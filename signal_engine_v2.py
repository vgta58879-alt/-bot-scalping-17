"""Moteur V2 HYBRIDE — Détection rapide + scoring qualité."""
import numpy as np
import pandas as pd
from utils import logger
from config import config

class SignalEngineV2:
    def __init__(self):
        self.min_candles = 30

    def add_indicators(self, df):
        if df is None or len(df) < self.min_candles:
            return None

        df = df.copy()
        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            if col not in df.columns:
                return None

        df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
        df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()

        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
        rs = gain / (loss + 1e-10)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["RSI"] = df["RSI"].fillna(50).clip(0, 100)

        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        df["Volume_MA"] = df["Volume"].rolling(20, min_periods=1).mean().replace(0, 1e-10)
        df["Volume_Ratio"] = df["Volume"] / df["Volume_MA"]

        hl = df["High"] - df["Low"]
        hc = np.abs(df["High"] - df["Close"].shift())
        lc = np.abs(df["Low"] - df["Close"].shift())
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["ATR_14"] = tr.rolling(14, min_periods=1).mean()
        df["ATR_14"] = df["ATR_14"].replace(0, df["Close"].iloc[-1] * 0.0005)

        df["Momentum_Up"] = df["EMA_9"] > df["EMA_21"]
        df["Momentum_Down"] = df["EMA_9"] < df["EMA_21"]

        df["Body"] = np.abs(df["Close"] - df["Open"])
        df["Range"] = df["High"] - df["Low"]
        df["Body_Pct"] = df["Body"] / (df["Range"] + 1e-10)

        return df

    def detect_direction(self, df_trend, df_confirm):
        if df_trend is None or df_confirm is None or len(df_trend) < 2 or len(df_confirm) < 2:
            return "NEUTRAL"

        try:
            confirm = df_confirm.iloc[-1]
            trend = df_trend.iloc[-1]
        except IndexError:
            return "NEUTRAL"

        score = 0
        if confirm.get("Momentum_Up", False):
            score += 2
        elif confirm.get("Momentum_Down", False):
            score -= 2

        rsi = confirm.get("RSI", 50)
        if rsi > 55: score += 1
        elif rsi < 45: score -= 1

        if confirm.get("Volume_Ratio", 1) > 1.2:
            score += 1 if confirm.get("Close", 0) > confirm.get("Open", 0) else -1

        if score >= 2: return "UP"
        elif score <= -2: return "DOWN"
        return "NEUTRAL"

    def find_entry_long(self, df_entry, df_confirm, pair):
        if df_entry is None or len(df_entry) < 5:
            return None

        last = df_entry.iloc[-1]
        prev = df_entry.iloc[-2]

        if pd.isna(last.get("Volume_Ratio")) or pd.isna(last.get("Body_Pct")):
            return None

        momentum_ok = True
        if df_confirm is not None and len(df_confirm) > 0:
            confirm_last = df_confirm.iloc[-1]
            if confirm_last.get("Momentum_Down", False) and confirm_last.get("RSI", 50) < 35:
                momentum_ok = False

        conditions = (
            last["Close"] > last["Open"] and
            last["Body_Pct"] > 0.40 and
            last["Volume_Ratio"] > 1.1 and
            momentum_ok
        )

        if not conditions:
            return None

        entry = round(float(last["Close"]), 8)
        atr = float(last["ATR_14"])

        prev_low = float(prev["Low"])
        sl_atr = round(entry - atr * 1.0, 8)
        sl = round(min(prev_low, sl_atr), 8)

        if sl >= entry:
            sl = round(entry - atr * 1.2, 8)

        dist = abs(entry - sl)
        if dist == 0:
            return None

        tp1 = round(entry + dist * 1.5, 8)
        tp2 = round(entry + dist * 2.0, 8)

        rr = abs(tp1 - entry) / dist
        if rr < config.MIN_RR_RATIO:
            return None

        return self._build_signal("LONG", entry, sl, tp1, tp2, rr, last, "HYBRID_BUY", pair)

    def find_entry_short(self, df_entry, df_confirm, pair):
        if df_entry is None or len(df_entry) < 5:
            return None

        last = df_entry.iloc[-1]
        prev = df_entry.iloc[-2]

        if pd.isna(last.get("Volume_Ratio")) or pd.isna(last.get("Body_Pct")):
            return None

        momentum_ok = True
        if df_confirm is not None and len(df_confirm) > 0:
            confirm_last = df_confirm.iloc[-1]
            if confirm_last.get("Momentum_Up", False) and confirm_last.get("RSI", 50) > 65:
                momentum_ok = False

        conditions = (
            last["Close"] < last["Open"] and
            last["Body_Pct"] > 0.40 and
            last["Volume_Ratio"] > 1.1 and
            momentum_ok
        )

        if not conditions:
            return None

        entry = round(float(last["Close"]), 8)
        atr = float(last["ATR_14"])

        prev_high = float(prev["High"])
        sl_atr = round(entry + atr * 1.0, 8)
        sl = round(max(prev_high, sl_atr), 8)

        if sl <= entry:
            sl = round(entry + atr * 1.2, 8)

        dist = abs(entry - sl)
        if dist == 0:
            return None

        tp1 = round(entry - dist * 1.5, 8)
        tp2 = round(entry - dist * 2.0, 8)

        rr = abs(tp1 - entry) / dist
        if rr < config.MIN_RR_RATIO:
            return None

        return self._build_signal("SHORT", entry, sl, tp1, tp2, rr, last, "HYBRID_SELL", pair)

    def _build_signal(self, direction, entry, sl, tp1, tp2, rr, last_candle, strategy, pair):
        confidence = 55
        if last_candle.get("Volume_Ratio", 1) > 1.5:
            confidence += 15
        if last_candle.get("Body_Pct", 0) > 0.6:
            confidence += 10
        if last_candle.get("Volume_Ratio", 1) > 2.0:
            confidence += 10
        confidence = min(confidence, 90)

        return {
            "id": f"{strategy}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
            "pair": pair,
            "direction": direction,
            "strategy": strategy,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "rr": round(rr, 2),
            "confidence": confidence,
            "timestamp": pd.Timestamp.now().isoformat(),
            "valid_until": (pd.Timestamp.now() + pd.Timedelta(minutes=config.SIGNAL_VALIDITY_MINUTES)).isoformat(),
            "status": "ACTIVE",
            "current_price": entry,
            "highest_price": entry if direction == "LONG" else entry,
            "lowest_price": entry if direction == "SHORT" else entry,
            "tp1_hit": False,
            "tp2_hit": False,
            "sl_hit": False,
            "be_moved": False,
            "pips": 0,
            "duration_minutes": 0,
        }

    def scan_pair(self, data, pair):
        df_entry = self.add_indicators(data.get("entry"))
        df_confirm = self.add_indicators(data.get("confirm"))
        df_trend = self.add_indicators(data.get("trend"))

        if df_entry is None:
            return None, None, None

        direction = self.detect_direction(df_trend, df_confirm)

        signal = None
        if direction == "UP":
            signal = self.find_entry_long(df_entry, df_confirm, pair)
            if signal:
                signal["market_direction"] = "UP"
        elif direction == "DOWN":
            signal = self.find_entry_short(df_entry, df_confirm, pair)
            if signal:
                signal["market_direction"] = "DOWN"
        else:
            # Même en NEUTRAL, si bougie très forte
            signal = self.find_entry_long(df_entry, df_confirm, pair)
            if signal:
                signal["market_direction"] = "NEUTRAL_UP"
            else:
                signal = self.find_entry_short(df_entry, df_confirm, pair)
                if signal:
                    signal["market_direction"] = "NEUTRAL_DOWN"

        return signal, df_entry, df_confirm

signal_engine = SignalEngineV2()
