"""Urgency Scanner — Déclenche un scan REST d'urgence quand le prix bouge fort.

LOGIQUE:
- WebSocket reçoit chaque tick en temps réel
- Si le prix bouge de >0.5% en 10 secondes sur une paire
  → Déclenche un scan REST IMMÉDIAT sur cette paire
  → Pas d'attente des 2 minutes
- Rate limit: max 1 scan d'urgence / paire / 2 minutes

C'est la solution au 'scan toutes les 6-12 secondes' sans 
se faire ban par l'API Binance.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from time_utils import now_utc
from utils import logger
from config import config

class UrgencyScanner:
    """
    Détecte les mouvements violents via WebSocket et déclenche
    un scan d'urgence REST sur la paire concernée.
    """

    def __init__(self, ws_feed, scan_callback):
        """
        Args:
            ws_feed: instance WebSocketFeed
            scan_callback: fonction async à appeler pour scanner une paire
        """
        self.ws = ws_feed
        self.scan_callback = scan_callback
        self.price_history = {}  # {pair: [(timestamp, price), ...]}
        self.last_urgency_scan = {}  # {pair: timestamp}
        self.running = False

        # Seuils de déclenchement
        self.threshold_pct = 0.5   # 0.5% de mouvement en 10s
        self.window_seconds = 10   # Fenêtre de 10 secondes
        self.cooldown_seconds = 120  # 2 min entre 2 scans d'urgence

    def record_price(self, pair, price):
        """Appelé à chaque tick WebSocket."""
        if pair not in self.price_history:
            self.price_history[pair] = []

        self.price_history[pair].append((now_utc(), price))

        # Garder seulement les prix des 30 dernières secondes
        cutoff = now_utc() - timedelta(seconds=30)
        self.price_history[pair] = [
            (t, p) for t, p in self.price_history[pair] if t > cutoff
        ]

        # Vérifier si mouvement violent
        self._check_urgency(pair, price)

    def _check_urgency(self, pair, current_price):
        """Vérifie si un scan d'urgence est nécessaire."""
        history = self.price_history.get(pair, [])
        if len(history) < 3:
            return

        # Prix il y a window_seconds
        cutoff = now_utc() - timedelta(seconds=self.window_seconds)
        old_prices = [(t, p) for t, p in history if t <= cutoff]
        if not old_prices:
            return

        old_price = old_prices[-1][1]  # Dernier prix avant la fenêtre
        if old_price == 0:
            return

        change_pct = abs(current_price - old_price) / old_price * 100

        if change_pct >= self.threshold_pct:
            # Vérifier cooldown
            last_scan = self.last_urgency_scan.get(pair)
            if last_scan:
                elapsed = (now_utc() - last_scan).total_seconds()
                if elapsed < self.cooldown_seconds:
                    return  # Cooldown actif

            # DÉCLENCHER SCAN D'URGENCE
            self.last_urgency_scan[pair] = now_utc()
            logger.warning(f"🚨 MOUVEMENT VIOLENT {pair}: {change_pct:.2f}% en {self.window_seconds}s")
            logger.warning(f"🚨 SCAN D'URGENCE DÉCLENCHÉ sur {pair}")

            # Déclencher le scan async
            asyncio.create_task(self._trigger_urgency_scan(pair))

    async def _trigger_urgency_scan(self, pair):
        """Lance le scan d'urgence sur une paire spécifique."""
        try:
            await self.scan_callback(pair)
        except Exception as e:
            logger.error(f"Erreur scan urgence {pair}: {e}")

    def get_stats(self):
        """Stats des scans d'urgence."""
        return {
            "pairs_monitored": list(self.price_history.keys()),
            "last_urgency": {p: t.isoformat() for p, t in self.last_urgency_scan.items()},
            "threshold_pct": self.threshold_pct,
            "window_seconds": self.window_seconds,
        }
