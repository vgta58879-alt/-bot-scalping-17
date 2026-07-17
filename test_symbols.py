#!/usr/bin/env python3
"""
🔍 TESTS PRÉ-DÉPLOIEMENT — Vérification UTC + Connexions

À exécuter EN LOCAL avant Replit.
Vérifie: UTC, Binance, symboles, klines, Telegram, WebSocket
"""

import asyncio, requests, sys
from datetime import datetime, timezone

BINANCE_URL = "https://fapi.binance.com"

def test_utc_alignment():
    print("\n🕐 TEST 0: Alignement UTC...")
    from time_utils import verify_utc_alignment
    ok = verify_utc_alignment()
    if not ok:
        print("   ⚠️  Le système n'est pas en UTC!")
        print("   ⚠️  Sur Replit: généralement OK (UTC par défaut)")
        print("   ⚠️  Sur VPS local: export TZ=UTC")
    return ok

def test_binance():
    print("\n🌐 Test 1: Connexion Binance...")
    try:
        resp = requests.get(f"{BINANCE_URL}/fapi/v1/ping", timeout=10)
        print(f"   {'✅' if resp.status_code == 200 else '❌'} Status {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"   ❌ {e}")
        return False

def test_symbols():
    print("\n📋 Test 2: Symboles disponibles...")
    try:
        resp = requests.get(f"{BINANCE_URL}/fapi/v1/exchangeInfo", timeout=15)
        data = resp.json()
        symbols = [s["symbol"] for s in data["symbols"] if s["status"] == "TRADING" and s["symbol"].endswith("USDT")]
        print(f"   ✅ {len(symbols)} paires USDT")

        from config import config
        missing = [p for p in config.PAIRS if p not in symbols]
        if missing:
            print(f"   ⚠️ MANQUANTES: {missing}")
        else:
            print(f"   ✅ Toutes les paires OK: {config.PAIRS}")
        return symbols
    except Exception as e:
        print(f"   ❌ {e}")
        return []

def test_klines(symbol="BTCUSDT"):
    print(f"\n📊 Test 3: Klines {symbol}...")
    try:
        resp = requests.get(f"{BINANCE_URL}/fapi/v1/klines", params={"symbol": symbol, "interval": "5m", "limit": 10}, timeout=10)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            # Vérifier que le timestamp est bien UTC
            last_time_ms = data[-1][0]
            last_time_utc = datetime.fromtimestamp(last_time_ms / 1000, tz=timezone.utc)
            print(f"   ✅ {len(data)} candles")
            print(f"   Dernière candle UTC: {last_time_utc.strftime('%H:%M:%S')}")
            print(f"   Heure UTC actuelle: {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
            return True
        print(f"   ❌ Réponse invalide")
        return False
    except Exception as e:
        print(f"   ❌ {e}")
        return False

def test_telegram():
    print("\n📱 Test 4: Telegram...")
    from config import config
    if not config.TELEGRAM_BOT_TOKEN:
        print("   ⚠️ Token non configuré")
        return False
    try:
        import telegram
        bot = telegram.Bot(token=config.TELEGRAM_BOT_TOKEN)
        async def send():
            await bot.send_message(chat_id=config.TELEGRAM_CHANNEL_ID, text="🤖 Test UTC OK")
        asyncio.run(send())
        print("   ✅ Message envoyé")
        return True
    except Exception as e:
        print(f"   ❌ {e}")
        return False

async def test_ws():
    print("\n🌐 Test 5: WebSocket...")
    try:
        import websockets
        async with websockets.connect("wss://fstream.binance.com/ws/btcusdt@aggTrade", timeout=10) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = __import__("json").loads(msg)
            print(f"   ✅ Prix WS: {data.get('p')}")
            return True
    except Exception as e:
        print(f"   ❌ {e}")
        return False

async def main():
    print("=" * 50)
    print("🔍 TESTS PRÉ-DÉPLOIEMENT — UTC STRICT")
    print("=" * 50)

    results = [
        ("UTC Alignment", test_utc_alignment()),
        ("Binance", test_binance()),
        ("Symboles", len(test_symbols()) > 0),
        ("Klines BTC", test_klines("BTCUSDT")),
        ("Klines XAU", test_klines("XAUUSDT")),
        ("Telegram", test_telegram()),
        ("WebSocket", await test_ws()),
    ]

    print("\n📊 RÉSULTATS")
    for name, ok in results:
        print(f"   {'✅ PASS' if ok else '❌ FAIL'} — {name}")

    all_ok = all(r[1] for r in results)
    print(f"\n{'🚀 Prêt pour Replit!' if all_ok else '⚠️ Corrige les erreurs.'}")
    return all_ok

if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
