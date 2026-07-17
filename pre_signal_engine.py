"""Pre-Signal Engine — Alerte préliminaire AVANT clôture M5.

LOGIQUE:
- WebSocket reçoit les ticks temps réel
- La candle M5 en cours est analysée en temps réel
- Si à 70%+ du temps de la candle, le mouvement est fort:
  → Envoie un PRE-SIGNAL (alerte, pas d'entrée)
- À la clôture M5 (5 min):
  → Si la bougie confirme → SIGNAL FINAL
  → Si la bougie retourne → ANNULATION

Le trader a 1-2 minutes pour se préparer.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from time_utils import now_utc, get_candle_time_utc
from utils import logger
from config import config

class PreSignalEngine:
    """
    Détecte les pre-signals sur la candle M5 en cours.

    Utilise les données WebSocket temps réel pour estimer
    la forme de la candle avant sa clôture.
    """

    def __init__(self, ws_feed, webhook_sender):
        self.ws = ws_feed
        self.sender = webhook_sender
        self.pre_signals = {}  # {pair: pre_signal_data}
        self.last_pre_signal = {}  # {pair: timestamp}
        self.running = False

        # Seuils
        self.min_progress_pct = 70   # 70% du temps de la candle écoulé
        self.min_body_pct = 0.6      # Corps projeté > 60% de la range
        self.min_volume_ratio = 1.3  # Volume > 130% moyenne
        self.cooldown_seconds = 300  # 5 min entre 2 pre-signals

    def get_candle_progress(self):
        """
        Retourne le pourcentage de temps écoulé de la candle M5 actuelle.
        0% = début de la candle, 100% = clôture imminente.
        """
        now = now_utc()
        minute = now.minute
        second = now.second

        # Début de la candle M5 actuelle
        candle_start_minute = (minute // 5) * 5
        candle_start = now.replace(minute=candle_start_minute, second=0, microsecond=0)

        # Temps écoulé en secondes
        elapsed = (now - candle_start).total_seconds()
        total = 300  # 5 minutes = 300 secondes

        progress = (elapsed / total) * 100
        return progress, candle_start

    def analyze_candle_in_progress(self, pair):
        """
        Analyse la candle M5 en cours via les données WebSocket.

        Returns:
            dict avec: open, high, low, current, body_pct, direction
            ou None si pas assez de données
        """
        # Récupérer les données de la candle en cours
        # On utilise le prix WebSocket + les données REST de la candle précédente
        current_price = self.ws.get_price(pair)
        if current_price is None:
            return None

        # Les open/high/low de la candle en cours ne sont pas disponibles
        # directement via WebSocket. On les estime:
        # - Open = prix au début de la candle (on le stocke)
        # - High = max des prix vus depuis le début
        # - Low = min des prix vus depuis le début

        if pair not in self.pre_signals:
            return None

        candle_data = self.pre_signals[pair]
        candle_open = candle_data.get("open", current_price)
        candle_high = max(candle_data.get("high", current_price), current_price)
        candle_low = min(candle_data.get("low", current_price), current_price)

        # Mettre à jour
        candle_data["high"] = candle_high
        candle_data["low"] = candle_low
        candle_data["current"] = current_price

        # Calculer body projeté
        range_candle = candle_high - candle_low
        if range_candle == 0:
            return None

        body = abs(current_price - candle_open)
        body_pct = body / range_candle

        direction = "LONG" if current_price > candle_open else "SHORT"

        return {
            "open": candle_open,
            "high": candle_high,
            "low": candle_low,
            "current": current_price,
            "body_pct": body_pct,
            "direction": direction,
            "range": range_candle,
        }

    def start_new_candle(self, pair, open_price):
        """Appelé au début de chaque nouvelle candle M5."""
        self.pre_signals[pair] = {
            "open": open_price,
            "high": open_price,
            "low": open_price,
            "current": open_price,
            "pre_signal_sent": False,
            "candle_start": now_utc(),
        }
        logger.info(f"📊 Nouvelle candle M5 {pair} @ {open_price}")

    async def check_pre_signal(self, pair):
        """
        Vérifie si un pre-signal doit être envoyé.
        Appelé régulièrement (toutes les 10-15 secondes).
        """
        progress, candle_start = self.get_candle_progress()

        # Vérifier cooldown
        last = self.last_pre_signal.get(pair)
        if last:
            elapsed = (now_utc() - last).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False, f"Cooldown pre-signal: {int(self.cooldown_seconds - elapsed)}s"

        # Vérifier progress minimum
        if progress < self.min_progress_pct:
            return False, f"Candle trop jeune: {progress:.0f}% (min {self.min_progress_pct}%)"

        # Analyser la candle en cours
        analysis = self.analyze_candle_in_progress(pair)
        if analysis is None:
            return False, "Pas assez de données WS"

        # Vérifier body projeté
        if analysis["body_pct"] < self.min_body_pct:
            return False, f"Body projeté faible: {analysis['body_pct']:.0%} (min {self.min_body_pct})"

        # Vérifier volume (on n'a pas le volume temps réel, on utilise un proxy)
        # Proxy: nombre de ticks reçus dans la fenêtre
        # Simplifié: on skip cette vérification pour le pre-signal

        # CONSTRUIRE LE PRE-SIGNAL
        pre_signal = {
            "id": f"PRE_{pair}_{now_utc().strftime('%Y%m%d_%H%M%S')}",
            "pair": pair,
            "direction": analysis["direction"],
            "strategy": "PRE_SIGNAL",
            "entry": round(analysis["current"], 8),
            "current_price": round(analysis["current"], 8),
            "confidence": int(analysis["body_pct"] * 100),
            "body_pct": round(analysis["body_pct"], 2),
            "candle_progress": round(progress, 1),
            "timestamp": now_utc().isoformat(),
            "pips": 0,
        }

        # Marquer comme envoyé
        if pair in self.pre_signals:
            self.pre_signals[pair]["pre_signal_sent"] = True
        self.last_pre_signal[pair] = now_utc()

        # ENVOYER
        logger.info(f"⚡ PRE-SIGNAL {pair}: {analysis['direction']} | Body {analysis['body_pct']:.0%} | {progress:.0f}% candle")
        await self.sender.send(pre_signal, signal_type="PRE_SIGNAL")

        return True, f"Pre-signal envoyé: {analysis['direction']} {pair}"

    async def run_loop(self):
        """Boucle de vérification des pre-signals."""
        self.running = True
        while self.running:
            try:
                for pair in config.PAIRS:
                    # Initialiser la candle si pas déjà fait
                    current_price = self.ws.get_price(pair)
                    if current_price and pair not in self.pre_signals:
                        self.start_new_candle(pair, current_price)

                    # Vérifier pre-signal
                    if current_price and pair in self.pre_signals:
                        # Vérifier si nouvelle candle (toutes les 5 min)
                        candle_start = self.pre_signals[pair].get("candle_start")
                        if candle_start:
                            elapsed = (now_utc() - candle_start).total_seconds()
                            if elapsed >= 300:  # Nouvelle candle
                                self.start_new_candle(pair, current_price)

                        # Envoyer pre-signal si conditions OK
                        await self.check_pre_signal(pair)

            except Exception as e:
                logger.error(f"Pre-signal erreur: {e}")

            await asyncio.sleep(15)  # Vérifie toutes les 15 secondes

    def stop(self):
        self.running = False

pre_signal_engine = None  # Initialisé dans main.py
