"""Signal Filter — Scoring + Noise Filter UTC.

Intègre:
- Scoring qualité (0-100)
- Noise filter (spread, congestion, flash crash)

NOTE: Le rate limiter/quota horaire est maintenant géré par signal_scheduler.py
"""
from noise_filter import noise_filter


class SignalFilter:
    """Filtre de scoring et anti-bruit."""

    def __init__(self):
        pass  # Plus de state de quota ici

    def calculate_score(self, signal, df_entry, df_confirm):
        """Calcule un score qualité de 0 à 100."""
        score = 0
        reasons = []

        last = df_entry.iloc[-1] if df_entry is not None and len(df_entry) > 0 else None
        confirm = df_confirm.iloc[-1] if df_confirm is not None and len(df_confirm) > 0 else None

        if last is None:
            return 0, ["Pas de données"]

        # Direction M15
        market_dir = signal.get("market_direction", "NEUTRAL")
        if market_dir in ["UP", "DOWN"]:
            score += 30
            reasons.append("Dir M15 alignée (+30)")
        elif market_dir in ["NEUTRAL_UP", "NEUTRAL_DOWN"]:
            score += 15
            reasons.append("Momentum neutre (+15)")

        # Volume
        vol_ratio = last.get("Volume_Ratio", 1)
        if vol_ratio > 2.0:
            score += 25
            reasons.append(f"Vol {vol_ratio:.1f}x (+25)")
        elif vol_ratio > 1.5:
            score += 20
            reasons.append(f"Vol {vol_ratio:.1f}x (+20)")
        elif vol_ratio > 1.2:
            score += 10
            reasons.append(f"Vol {vol_ratio:.1f}x (+10)")

        # Corps bougie
        body_pct = last.get("Body_Pct", 0)
        if body_pct > 0.7:
            score += 20
            reasons.append(f"Corps {body_pct:.0%} (+20)")
        elif body_pct > 0.5:
            score += 15
            reasons.append(f"Corps {body_pct:.0%} (+15)")
        elif body_pct > 0.4:
            score += 10
            reasons.append(f"Corps {body_pct:.0%} (+10)")

        # RSI
        rsi = last.get("RSI", 50)
        if signal["direction"] == "LONG":
            if 45 < rsi < 70:
                score += 15
                reasons.append(f"RSI {rsi:.0f} (+15)")
            elif 40 < rsi < 75:
                score += 10
                reasons.append(f"RSI {rsi:.0f} (+10)")
        else:
            if 30 < rsi < 55:
                score += 15
                reasons.append(f"RSI {rsi:.0f} (+15)")
            elif 25 < rsi < 60:
                score += 10
                reasons.append(f"RSI {rsi:.0f} (+10)")

        # ATR
        atr = last.get("ATR_14", 0)
        price = last.get("Close", 1)
        atr_pct = (atr / price) * 100 if price > 0 else 0
        if atr_pct > 0.05:
            score += 10
            reasons.append(f"ATR {atr_pct:.3f}% (+10)")

        # Confiance
        conf = signal.get("confidence", 50)
        if conf > 75:
            score += 5
            reasons.append(f"Conf {conf}% (+5)")

        return min(score, 100), reasons

    def validate_noise(self, signal, df_entry, pair):
        """Applique les filtres anti-bruit."""
        valid, reason, details = noise_filter.validate(signal, df_entry, pair)
        return valid, reason, details

    def get_stats(self):
        """Stats simplifiées (scoring uniquement)."""
        return {"status": "scoring_only"}


signal_filter = SignalFilter()
