#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
  🤖 SCALPING BOT V2 FINAL — SCHEDULER QUOTA (3 signaux/heure UTC)
═══════════════════════════════════════════════════════════════════
"""

import asyncio, threading
from flask import Flask

from config import config
from utils import logger
from time_utils import (
    now_utc, format_utc_full, verify_utc_alignment,
    get_current_hour_utc, get_current_session_utc
)
from binance_client import binance_client
from websocket_feed import ws_feed
from signal_engine_v2 import signal_engine
from risk_manager_v2 import risk_manager
from signal_filter import signal_filter
from signal_scheduler import signal_scheduler
from trade_tracker_v2 import TradeTrackerV2
from telegram_bot_v2 import telegram_bot
from webhook_sender import webhook_sender
from urgency_scanner import UrgencyScanner
from pre_signal_engine import PreSignalEngine

app = Flask(__name__)

@app.route("/")
def home():
    stats = risk_manager.stats()
    active = risk_manager.active()
    paused, until = risk_manager.is_paused()
    ws_status = "🟢" if ws_feed.price_cache else "🔴"
    sched = signal_scheduler.get_stats()
    session_name, session_ok = get_current_session_utc()
    return f"""
    <h1>🤖 Scalping Bot V2 FINAL</h1>
    <p><b>UTC:</b> {now_utc().strftime('%H:%M:%S')}</p>
    <p><b>Session:</b> {session_name} {'✅' if session_ok else '❌'}</p>
    <p><b>Status:</b> {'⏸️ PAUSE' if paused else '🟢 ACTIF'}</p>
    <p><b>WS:</b> {ws_status}</p>
    <p><b>Trades:</b> {len(active)}/3</p>
    <p><b>Win Rate:</b> {stats['win_rate']}%</p>
    <p><b>Quota:</b> {sched['sent']}/3 | Slot {sched['current_slot']}/3 | Seuil {sched['threshold']}</p>
    <hr><p><i>/scan | /stats | /health</i></p>
    """

@app.route("/health")
def health():
    return {"status": "ok", "ws": bool(ws_feed.price_cache), "utc": now_utc().isoformat()}, 200

@app.route("/stats")
def stats():
    s = risk_manager.stats()
    s["scheduler"] = signal_scheduler.get_stats()
    s["utc"] = now_utc().isoformat()
    return s, 200

@app.route("/scan")
def scan_endpoint():
    asyncio.run_coroutine_threadsafe(run_scan(), loop)
    return {"status": "scan_triggered"}, 200


async def run_scan():
    logger.info("=" * 60)
    logger.info(f"🔍 SCAN — {format_utc_full()}")

    paused, until = risk_manager.is_paused()
    if paused:
        logger.warning(f"⏸️ Pause: {until}")
        return

    # 1. Update trades
    tracker = TradeTrackerV2(risk_manager, ws_feed, telegram_bot)
    updates = await tracker.update_all()
    for msg_type, msg_text, sig in updates:
        await webhook_sender.send(sig, signal_type=msg_type)

    # 2. Check quota
    needed = signal_scheduler.get_signals_needed()
    if needed <= 0:
        logger.info("⏳ Quota atteint — skip")
        return
    logger.info(f"📊 Quota: {needed}/3 restants | Slot {signal_scheduler.get_current_slot()[0] + 1}")

    # 3. Scan paires
    detected_signals = []
    for pair in config.PAIRS:
        logger.info(f"🔎 Scan {pair}...")
        data = await binance_client.get_multi_timeframe(pair)
        if data["entry"] is None:
            continue
        signal, df_entry, df_confirm = signal_engine.scan_pair(data, pair)
        if signal is None:
            continue

        # Noise filter
        noise_ok, noise_reason, noise_details = signal_filter.validate_noise(signal, df_entry, pair)
        logger.info(f"   🔇 Noise: {noise_reason}")
        if not noise_ok:
            logger.info(f"   🚫 REJETÉ: {noise_reason}")
            continue

        # Risk
        can_trade, reason = risk_manager.can_trade(signal)
        if not can_trade:
            logger.info(f"   🚫 Risk: {reason}")
            continue

        # Score
        score, score_reasons = signal_filter.calculate_score(signal, df_entry, df_confirm)
        signal["_score"] = score
        signal["_score_reasons"] = score_reasons
        logger.info(f"   📊 Score: {score}/100")

        # Store in scheduler
        signal_scheduler.add_detected(signal, score)
        detected_signals.append(signal)

    if not detected_signals:
        logger.info("Aucun setup.")
        return

    # 4. Adaptive threshold
    threshold = signal_scheduler.adapt_threshold()
    logger.info(f"📊 Seuil: {threshold}")

    # 5. Get BEST pending signals from ENTIRE hour (not just this scan)
    pending = signal_scheduler.get_pending_signals(threshold=threshold, count=needed)
    logger.info(f"📊 {len(pending)} en attente | {len(detected_signals)} détectés ce scan")

    # 6. Send by slots
    sent_count = 0
    for signal in pending:
        if sent_count >= needed:
            break
        should_send, reason = signal_scheduler.should_send_now(signal, signal.get("_score", 0))
        if not should_send:
            logger.info(f"   ⏳ {reason}")
            continue
        await webhook_sender.send(signal, signal_type="SIGNAL")
        risk_manager.add(signal)
        signal_scheduler.register_sent(signal)
        sent_count += 1
        logger.info(f"✅ ENVOYÉ: {signal['pair']} | Score {signal['_score']}/100 | {sent_count}/{needed}")

    logger.info(f"Terminé. {sent_count} envoyé(s).")

    # Rapport auto
    if get_current_hour_utc() in [0, 6, 12, 18] and now_utc().minute < 5:
        stats = risk_manager.stats()
        await webhook_sender.send({"result": "STATS", **stats}, signal_type="UPDATE")


async def urgency_scan_callback(pair):
    logger.warning(f"🚨 URGENCE {pair}")
    needed = signal_scheduler.get_signals_needed()
    if needed <= 0:
        return
    data = await binance_client.get_multi_timeframe(pair)
    if data["entry"] is None:
        return
    signal, df_entry, df_confirm = signal_engine.scan_pair(data, pair)
    if signal is None:
        return
    noise_ok, _, _ = signal_filter.validate_noise(signal, df_entry, pair)
    if not noise_ok:
        return
    can_trade, _ = risk_manager.can_trade(signal)
    if not can_trade:
        return
    score, _ = signal_filter.calculate_score(signal, df_entry, df_confirm)
    signal["_score"] = score
    signal_scheduler.add_detected(signal, score)
    should_send, reason = signal_scheduler.should_send_now(signal, score)
    if not should_send:
        return
    signal["strategy"] = "URGENCY"
    await webhook_sender.send(signal, signal_type="SIGNAL")
    risk_manager.add(signal)
    signal_scheduler.register_sent(signal)
    logger.info(f"🚨 URGENCE ENVOYÉ: {pair} | {score}/100")


async def tracker_loop():
    tracker = TradeTrackerV2(risk_manager, ws_feed, telegram_bot)
    while True:
        try:
            updates = await tracker.update_all()
            for msg_type, msg_text, sig in updates:
                await webhook_sender.send(sig, signal_type=msg_type)
        except Exception as e:
            logger.error(f"Tracker: {e}")
        await asyncio.sleep(1)


async def scheduler_loop():
    while True:
        await run_scan()
        await asyncio.sleep(120)


async def ws_loop():
    await ws_feed.connect()


async def pre_signal_loop():
    global pre_signal_engine
    pre_signal_engine = PreSignalEngine(ws_feed, webhook_sender)
    await pre_signal_engine.run_loop()


async def ws_price_monitor():
    urgency = UrgencyScanner(ws_feed, urgency_scan_callback)
    while True:
        try:
            for pair in config.PAIRS:
                price = ws_feed.get_price(pair)
                if price:
                    urgency.record_price(pair, price)
        except Exception as e:
            logger.error(f"WS monitor: {e}")
        await asyncio.sleep(5)


def start_flask():
    app.run(host="0.0.0.0", port=8080, debug=False)


loop = asyncio.new_event_loop()
pre_signal_engine = None

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 BOT V2 FINAL — SCHEDULER QUOTA")
    print("=" * 60)
    utc_ok = verify_utc_alignment()
    if not utc_ok:
        print("⚠️ Serveur non UTC")
    print()
    print(f"🕐 UTC: {format_utc_full()}")
    print(f"📡 Paires: {config.PAIRS}")
    print(f"🔇 Noise | Quota: 3/h UTC | Slots: 0-20-40")
    logger.info("🚀 DÉMARRAGE")
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask:8080")
    asyncio.set_event_loop(loop)
    tasks = [
        loop.create_task(ws_loop()),
        loop.create_task(ws_price_monitor()),
        loop.create_task(pre_signal_loop()),
        loop.create_task(tracker_loop()),
        loop.create_task(scheduler_loop()),
    ]
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt")
        for t in tasks:
            t.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.run_until_complete(binance_client.close())
        loop.run_until_complete(ws_feed.stop())
        if pre_signal_engine:
            pre_signal_engine.stop()
        loop.run_until_complete(webhook_sender.close())
        loop.close()
