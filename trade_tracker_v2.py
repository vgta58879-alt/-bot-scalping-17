"""Trade Tracker V2 — Suivi temps réel, timestamps UTC."""
from datetime import datetime, timezone, timedelta
from time_utils import now_utc, format_utc_full
from utils import logger, price_to_points
from config import config

class TradeTrackerV2:
    def __init__(self, risk_manager, ws_feed, telegram_sender):
        self.rm = risk_manager
        self.ws = ws_feed
        self.send = telegram_sender
        self.last_update = {}

    def _price_to_points(self, price_change, pair):
        if "XAU" in pair:
            return round(price_change * 100, 2)
        elif "XAG" in pair:
            return round(price_change * 100, 2)
        elif "BTC" in pair:
            return round(price_change, 2)
        elif "ETH" in pair:
            return round(price_change * 100, 2)
        return round(price_change * 100, 2)

    async def update_all(self):
        active = self.rm.active()
        messages = []

        for sig in active:
            pair = sig["pair"]
            direction = sig["direction"]

            current_price = self.ws.get_price(pair)
            if current_price is None:
                continue

            updates = {
                "current_price": current_price,
                "duration_minutes": sig.get("duration_minutes", 0) + 1,
            }

            if direction == "LONG":
                if current_price > sig.get("highest_price", sig["entry"]):
                    updates["highest_price"] = current_price
            else:
                if current_price < sig.get("lowest_price", sig["entry"]):
                    updates["lowest_price"] = current_price

            price_change = current_price - sig["entry"]
            if direction == "SHORT":
                price_change = -price_change
            points = self._price_to_points(price_change, pair)
            updates["pips"] = round(points, 2)

            # TP1
            if not sig.get("tp1_hit"):
                tp1_reached = (direction == "LONG" and current_price >= sig["tp1"]) or                               (direction == "SHORT" and current_price <= sig["tp1"])
                if tp1_reached:
                    updates["tp1_hit"] = True
                    be_sl = sig["entry"] + (0.01 if direction == "LONG" else -0.01)
                    updates["sl"] = round(be_sl, 8)
                    updates["be_moved"] = True
                    msg = self._format_be(sig, current_price, points)
                    messages.append(("BE", msg, sig))

            # TP2
            if sig.get("tp1_hit") and not sig.get("tp2_hit"):
                tp2_reached = (direction == "LONG" and current_price >= sig["tp2"]) or                               (direction == "SHORT" and current_price <= sig["tp2"])
                if tp2_reached:
                    updates["tp2_hit"] = True
                    updates["status"] = "CLOSED"
                    closed = self.rm.close(sig["id"], "TP2", points)
                    msg = self._format_close(closed, "TP2", points)
                    messages.append(("CLOSE", msg, sig))
                    continue

            # SL
            sl_hit = (direction == "LONG" and current_price <= sig["sl"]) or                      (direction == "SHORT" and current_price >= sig["sl"])
            if sl_hit:
                updates["sl_hit"] = True
                updates["status"] = "CLOSED"
                closed = self.rm.close(sig["id"], "SL", points)
                msg = self._format_close(closed, "SL", points)
                messages.append(("CLOSE", msg, sig))
                continue

            # Stagnation 10 min
            if updates["duration_minutes"] > 10:
                if abs(points) < 1:
                    updates["status"] = "CLOSED"
                    closed = self.rm.close(sig["id"], "CANCELLED", points)
                    msg = self._format_close(closed, "CANCELLED", points)
                    messages.append(("CLOSE", msg, sig))
                    continue

            # Expiration 5 min UTC
            valid_until = sig.get("valid_until")
            if valid_until:
                try:
                    vt = datetime.fromisoformat(valid_until)
                    if vt.tzinfo is None:
                        vt = vt.replace(tzinfo=timezone.utc)
                    if now_utc() > vt and not sig.get("tp1_hit"):
                        updates["status"] = "CLOSED"
                        closed = self.rm.close(sig["id"], "EXPIRED", points)
                        msg = self._format_close(closed, "EXPIRED", points)
                        messages.append(("CLOSE", msg, sig))
                        continue
                except:
                    pass

            self.rm.update(sig["id"], updates)

            last_up = self.last_update.get(sig["id"])
            if last_up is None:
                should_update = True
            else:
                try:
                    lu = datetime.fromisoformat(last_up)
                    if lu.tzinfo is None:
                        lu = lu.replace(tzinfo=timezone.utc)
                    should_update = (now_utc() - lu).total_seconds() > 120
                except:
                    should_update = True

            if should_update:
                if abs(points) >= 2 or abs(points) <= -1:
                    msg = self._format_update(sig, current_price, points)
                    messages.append(("UPDATE", msg, sig))
                    self.last_update[sig["id"]] = now_utc().isoformat()

        return messages

    def _format_be(self, sig, price, points):
        emoji = "🟢" if sig["direction"] == "LONG" else "🔴"
        metal = "🥇" if "XAU" in sig["pair"] else ""
        return f"""{emoji} {metal} 🔒 TP1 — SL AU BE

📊 {sig['pair']} | {sig['direction']}
💰 {price} | {points:+.2f} pts
🔒 SL: {sig['entry']} (BE)
🎯 TP2: {sig['tp2']}

✅ SANS RISQUE
"""

    def _format_close(self, sig, result, points):
        emojis = {"TP2": "🟢🟢", "TP1": "🟢", "SL": "🔴", "CANCELLED": "⚪", "EXPIRED": "⚪"}
        emoji = emojis.get(result, "⚪")
        metal = "🥇" if "XAU" in sig["pair"] else ""
        dur = sig.get("duration_minutes", 0)
        return f"""{emoji} {metal} CLÔTURÉ — {sig['pair']}

{sig['direction']} | {result} | {points:+.2f} pts
⏱️ {dur} min | {sig['strategy']}

📈 WR: {self.rm.stats()['win_rate']}% | {self.rm.stats()['total_pips']} pts
"""

    def _format_update(self, sig, price, points):
        emoji = "🟢" if points > 0 else "🔴"
        metal = "🥇" if "XAU" in sig["pair"] else ""
        return f"""{emoji} {metal} {sig['pair']} | {sig['direction']}
💰 {price} | {points:+.2f} pts
🛑 {sig['sl']} | 🎯 {sig['tp1']}
"""
