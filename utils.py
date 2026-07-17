"""Utils — Logger, JSON helpers, etc."""
import os
import json
import logging
from datetime import datetime, timezone

# ─── CONFIGURATION DU LOGGER ───
LOGS_DIR = os.path.join(os.path.dirname(__file__), "data")
LOGS_FILE = os.path.join(LOGS_DIR, "bot.log")

# Créer le dossier data/ s'il n'existe pas (essentiel pour Render)
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scalping_bot")


# ─── JSON HELPERS ───
def load_json(filepath, default=None):
    """Charge un fichier JSON ou retourne la valeur par défaut."""
    # Créer le dossier parent si nécessaire
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}


def save_json(filepath, data):
    """Sauvegarde un fichier JSON (crée les dossiers si besoin)."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
