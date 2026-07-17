"""Configuration centralisée — Scalping Bot V2 HYBRIDE UTC."""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
    BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")
    BINANCE_WS_URL = os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com/ws")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "1.0"))
    MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "3"))
    MAX_DAILY_LOSSES = int(os.getenv("MAX_DAILY_LOSSES", "5"))
    PAUSE_AFTER_CONSECUTIVE_SL = int(os.getenv("PAUSE_AFTER_CONSECUTIVE_SL", "3"))
    MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", "1.2"))

    TF_ENTRY = os.getenv("TF_ENTRY", "5m")
    TF_CONFIRM = os.getenv("TF_CONFIRM", "15m")
    TF_TREND = os.getenv("TF_TREND", "1h")

    PAIRS_RAW = os.getenv("PAIRS", "BTCUSDT,ETHUSDT,XAUUSDT")
    PAIRS = [p.strip().upper() for p in PAIRS_RAW.split(",")]

    # ─── SESSIONS UTC (alignées MT5) ───
    # MT5 affiche UTC+0 pour les candles
    # Ces horaires correspondent aux sessions forex en UTC
    SESSIONS = {
        "asia": (0, 4),        # 00:00-04:00 UTC — Tokyo
        "london_pre": (6, 8),  # 06:00-08:00 UTC — Pré-London
        "london": (8, 12),     # 08:00-12:00 UTC — London
        "ny_pre": (12, 14),    # 12:00-14:00 UTC — Pré-NY
        "ny": (14, 17),        # 14:00-17:00 UTC — New York
        "ny_late": (17, 20),   # 17:00-20:00 UTC — Fin NY
    }

    DATA_DIR = "data"
    TRADES_FILE = f"{DATA_DIR}/trades.json"
    STATS_FILE = f"{DATA_DIR}/stats.json"
    LOGS_FILE = f"{DATA_DIR}/bot.log"

    SIGNAL_VALIDITY_MINUTES = 5
    STAGNATION_CANDLES = 2
    COOLDOWN_MINUTES = 15
    BE_TRIGGER_PIPS = 5

    CORRELATIONS = {}

config = Config()
