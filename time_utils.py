"""Gestion du temps UTC — Alignement strict avec MT5.

MT5 utilise UTC+0 (temps universel coordonné) pour:
- Les timestamps des candles (Open Time, Close Time)
- Le calendrier économique
- Les indicateurs temps réel

Ce module garantit que le bot est 100% aligné sur UTC,
quelle que soit la timezone du serveur (Replit, VPS, local).
"""
import time
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────
# VÉRIFICATION AU DÉMARRAGE
# ─────────────────────────────────────────────

def get_system_timezone():
    """Détecte la timezone du système."""
    import os
    tz = os.environ.get('TZ', 'non définie')
    offset = time.timezone if time.daylight == 0 else time.altzone
    offset_hours = -offset / 3600
    return tz, offset_hours

def verify_utc_alignment():
    """
    Vérifie que le système est bien aligné sur UTC.
    À appeler au démarrage du bot.
    """
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)

    # Si la différence entre local et UTC > 1 min → problème
    diff = abs((now_local.replace(tzinfo=None) - now_utc.replace(tzinfo=None)).total_seconds())

    tz_name, tz_offset = get_system_timezone()

    print(f"🕐 VÉRIFICATION TIMEZONE")
    print(f"   TZ système: {tz_name}")
    print(f"   Offset: UTC{tz_offset:+.1f}")
    print(f"   Heure locale: {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Heure UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Différence: {diff:.0f} secondes")

    if diff > 60:
        print(f"   ⚠️ ALERTE: Le système n'est pas en UTC!")
        print(f"   ⚠️ Les candles MT5 ne seront pas alignées!")
        return False
    else:
        print(f"   ✅ Système aligné sur UTC")
        return True

# ─────────────────────────────────────────────
# FONCTIONS TEMPS UTC STRICT
# ─────────────────────────────────────────────

def now_utc():
    """Retourne l'heure UTC actuelle avec timezone aware."""
    return datetime.now(timezone.utc)

def now_utc_naive():
    """Retourne l'heure UTC sans timezone (pour comparaisons)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def utc_timestamp():
    """Timestamp Unix UTC."""
    return datetime.now(timezone.utc).timestamp()

def format_utc(dt=None, fmt="%H:%M:%S"):
    """Formate une datetime en UTC."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        # Si naive, assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(fmt)

def format_utc_full(dt=None):
    """Format complet UTC pour logs."""
    return format_utc(dt, "%Y-%m-%d %H:%M:%S UTC")

def parse_utc(iso_string):
    """Parse une string ISO en datetime UTC aware."""
    if iso_string.endswith('Z'):
        iso_string = iso_string[:-1] + '+00:00'
    dt = datetime.fromisoformat(iso_string)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# ─────────────────────────────────────────────
# SESSIONS MT5 (UTC)
# ─────────────────────────────────────────────

MT5_SESSIONS = {
    "asia": (0, 4),        # 00:00 - 04:00 UTC (Tokyo)
    "london_pre": (6, 8),  # 06:00 - 08:00 UTC (pré-London)
    "london": (8, 12),     # 08:00 - 12:00 UTC (London)
    "ny_pre": (12, 14),    # 12:00 - 14:00 UTC (pré-NY)
    "ny": (14, 17),        # 14:00 - 17:00 UTC (NY)
    "ny_late": (17, 20),   # 17:00 - 20:00 UTC (fin NY)
}

def get_current_session_utc():
    """Retourne la session de trading actuelle en UTC."""
    hour = datetime.now(timezone.utc).hour
    for name, (start, end) in MT5_SESSIONS.items():
        if start <= hour < end:
            return name, True
    return "hors_session", False

def is_session_active_utc(sessions_dict):
    """
    Vérifie si on est dans une session active (UTC).

    Args:
        sessions_dict: dict {name: (start_hour, end_hour)} en UTC
    """
    now = datetime.now(timezone.utc)
    hour = now.hour
    for name, (start, end) in sessions_dict.items():
        if start <= hour < end:
            return True, name
    return False, None

def get_candle_time_utc(interval_minutes=5):
    """
    Retourne l'heure de début de la candle M5 actuelle en UTC.
    Utile pour vérifier l'alignement avec MT5.
    """
    now = datetime.now(timezone.utc)
    minute = (now.minute // interval_minutes) * interval_minutes
    candle_time = now.replace(minute=minute, second=0, microsecond=0)
    return candle_time

def time_until_next_candle(interval_minutes=5):
    """Temps restant avant la prochaine candle M5 UTC."""
    now = datetime.now(timezone.utc)
    next_minute = ((now.minute // interval_minutes) + 1) * interval_minutes
    if next_minute >= 60:
        next_time = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
    else:
        next_time = now.replace(minute=next_minute, second=0, microsecond=0)
    return (next_time - now).total_seconds()

# ─────────────────────────────────────────────
# RATE LIMITER UTC
# ─────────────────────────────────────────────

def get_current_hour_utc():
    """Heure UTC actuelle (0-23)."""
    return datetime.now(timezone.utc).hour

def get_current_minute_utc():
    """Minute UTC actuelle (0-59)."""
    return datetime.now(timezone.utc).minute

def minutes_until_next_hour_utc():
    """Minutes restantes avant la prochaine heure UTC."""
    now = datetime.now(timezone.utc)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return int((next_hour - now).total_seconds() / 60)

# ─────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("🕐 TESTS TIME_UTILS UTC")
    print("=" * 50)

    verify_utc_alignment()

    print(f"\n📍 now_utc(): {now_utc()}")
    print(f"📍 Session active: {get_current_session_utc()}")
    print(f"📍 Candle M5 actuelle: {get_candle_time_utc()}")
    print(f"📍 Temps avant prochaine candle: {time_until_next_candle():.0f}s")
    print(f"📍 Heure UTC: {get_current_hour_utc()}h{get_current_minute_utc():02d}")
    print(f"📍 Minutes avant prochaine heure: {minutes_until_next_hour_utc()}")
