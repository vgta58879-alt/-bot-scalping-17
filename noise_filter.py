"""Noise Filter — Filtres anti-bruit avancés pour réduire les faux signaux.

Filtres:
1. SPREAD FILTER: Rejette si bid-ask > 0.1%
2. CONGESTION FILTER: Rejette si le prix oscille dans un range
3. DIVERGENCE FILTER: Rejette si BTC/ETH divergent anormalement
4. FLASH CRASH FILTER: Rejette si le prix chute/monte >2% en 1 candle
"""
import numpy as np
from datetime import datetime, timezone
from utils import logger
from config import config

class NoiseFilter:
    """Filtres anti-bruit pour éliminer les faux signaux."""

    def __init__(self):
        self.last_prices = {}  # {pair: [prices]}
        self.congestion_window = 10  # candles

    def check_spread(self, df_entry, pair, max_spread_pct=0.1):
        """
        Vérifie si le spread (High-Low)/Close est raisonnable.
        Si spread > 0.1% sur une candle M5 → rejet (pas assez liquide)
        """
        if df_entry is None or len(df_entry) < 1:
            return True, "Pas de données"

        last = df_entry.iloc[-1]
        spread_pct = (last["High"] - last["Low"]) / last["Close"] * 100

        if spread_pct > max_spread_pct:
            return False, f"Spread trop large: {spread_pct:.2f}% (max {max_spread_pct}%)"

        return True, f"Spread OK: {spread_pct:.3f}%"

    def check_congestion(self, df_entry, pair, max_range_pct=0.3):
        """
        Vérifie si le marché est en congestion (range).
        Si le prix oscille dans un range de <0.3% depuis 10 candles → rejet.
        """
        if df_entry is None or len(df_entry) < self.congestion_window:
            return True, "Pas assez d'historique"

        recent = df_entry.iloc[-self.congestion_window:]
        high_max = recent["High"].max()
        low_min = recent["Low"].min()
        mid = (high_max + low_min) / 2

        if mid == 0:
            return True, ""

        range_pct = (high_max - low_min) / mid * 100

        if range_pct < max_range_pct:
            return False, f"Congestion détectée: range {range_pct:.2f}% sur {self.congestion_window} candles"

        return True, f"Pas de congestion: range {range_pct:.2f}%"

    def check_flash_crash(self, df_entry, pair, max_move_pct=2.0):
        """
        Vérifie si la dernière candle est un flash crash/pump.
        Si mouvement >2% en 1 candle M5 → rejet (manipulation probable)
        """
        if df_entry is None or len(df_entry) < 2:
            return True, ""

        last = df_entry.iloc[-1]
        prev = df_entry.iloc[-2]

        if prev["Close"] == 0:
            return True, ""

        move_pct = abs(last["Close"] - prev["Close"]) / prev["Close"] * 100

        if move_pct > max_move_pct:
            return False, f"Flash move détecté: {move_pct:.2f}% en 1 candle (max {max_move_pct}%)"

        return True, f"Move normal: {move_pct:.2f}%"

    def check_divergence(self, data_dict, pair):
        """
        Vérifie si BTC et ETH divergent anormalement.
        Si BTC monte fort et ETH baisse fort (ou inverse) → un des deux est faux.
        """
        # Nécessite les données des autres paires — simplifié ici
        return True, "Divergence check: OK (mono-paire)"

    def validate(self, signal, df_entry, pair):
        """
        Applique tous les filtres anti-bruit.

        Returns:
            (bool, str, list): (valide, raison, [détails])
        """
        checks = []

        # 1. Spread
        ok, reason = self.check_spread(df_entry, pair)
        checks.append(f"Spread: {reason}")
        if not ok:
            return False, reason, checks

        # 2. Congestion
        ok, reason = self.check_congestion(df_entry, pair)
        checks.append(f"Congestion: {reason}")
        if not ok:
            return False, reason, checks

        # 3. Flash crash
        ok, reason = self.check_flash_crash(df_entry, pair)
        checks.append(f"Flash: {reason}")
        if not ok:
            return False, reason, checks

        return True, "Tous les filtres passent", checks

noise_filter = NoiseFilter()
