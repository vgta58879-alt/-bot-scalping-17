"""Utilitaires communs — Toutes les fonctions temps via time_utils UTC."""
import json, os, logging, hmac, hashlib
from datetime import datetime, timezone, timedelta
from config import config

# Import des fonctions UTC strictes
from time_utils import now_utc, format_utc_full, parse_utc, utc_timestamp

# Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scalping_bot_v2")

def load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return default

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

# ─── Fonctions temps OBSOLÈTES — redirigées vers time_utils ───
# NE PAS utiliser datetime.now() sans timezone!
# NE PAS utiliser datetime.now(timezone.utc) directement!
# TOUJOURS utiliser now_utc() de time_utils

def binance_signature(query_string, secret):
    """Génère la signature HMAC SHA256 pour Binance."""
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def calculate_position_size(capital, risk_percent, entry, sl, pair):
    """Calcule la taille de position en USDT."""
    risk_amount = capital * (risk_percent / 100)
    sl_distance = abs(entry - sl)
    if sl_distance == 0:
        return 0
    position_size = risk_amount / sl_distance * entry
    return round(position_size, 2)

def price_to_points(price_change, pair):
    """Convertit changement de prix en points selon la paire."""
    if "XAU" in pair:
        return round(price_change * 100, 2)
    elif "XAG" in pair:
        return round(price_change * 100, 2)
    elif "BTC" in pair:
        return round(price_change, 2)
    elif "ETH" in pair:
        return round(price_change * 100, 2)
    return round(price_change * 100, 2)
