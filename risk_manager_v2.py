"""Risk Manager V2 — Tous les timestamps en UTC aware."""
from time_utils import now_utc, format_utc_full
from utils import logger, load_json, save_json
from config import config

class RiskManagerV2:
    def __init__(self):
        self.state_file = f"{config.DATA_DIR}/risk_state_v2.json"
        self.state = load_json(self.state_file, {
            "daily_losses": 0,
            "consecutive_sl": 0,
            "last_reset_utc": now_utc().isoformat(),
            "paused_until_utc": None,
            "active_signals": [],
            "last_signal_time_utc": {},
            "daily_stats": {"wins": 0, "losses": 0, "pips": 0}
        })

    def _save(self):
        save_json(self.state_file, self.state)

    def reset_daily(self):
        self.state["daily_losses"] = 0
        self.state["consecutive_sl"] = 0
        self.state["paused_until_utc"] = None
        self.state["daily_stats"] = {"wins": 0, "losses": 0, "pips": 0}
        self.state["last_reset_utc"] = now_utc().isoformat()
        self._save()
        logger.info("🔄 Reset quotidien UTC")

    def is_paused(self):
        if self.state.get("paused_until_utc"):
            from datetime import datetime, timezone
            pause_dt = self.state["paused_until_utc"]
            if isinstance(pause_dt, str):
                pause_dt = datetime.fromisoformat(pause_dt)
            if pause_dt.tzinfo is None:
                pause_dt = pause_dt.replace(tzinfo=timezone.utc)
            if now_utc() < pause_dt:
                return True, pause_dt.isoformat()
            self.state["paused_until_utc"] = None
            self._save()
        return False, None

    def can_trade(self, signal):
        paused, until = self.is_paused()
        if paused:
            return False, f"⏸️ Pause jusqu'à {until}"

        active = [s for s in self.state["active_signals"] if s["status"] == "ACTIVE"]
        if len(active) >= config.MAX_CONCURRENT_TRADES:
            return False, f"🚫 Max {config.MAX_CONCURRENT_TRADES} trades actifs"

        pair_active = [s for s in active if s["pair"] == signal["pair"]]
        if pair_active:
            return False, f"🚫 Trade actif sur {signal['pair']}"

        # Cooldown 15 min UTC
        pair = signal["pair"]
        last_time = self.state["last_signal_time_utc"].get(pair)
        if last_time:
            from datetime import datetime, timezone
            last_dt = datetime.fromisoformat(last_time) if isinstance(last_time, str) else last_time
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (now_utc() - last_dt).total_seconds() / 60
            if elapsed < 15:
                return False, f"⏳ Cooldown {pair} — {int(15 - elapsed)} min"

        if self.state["daily_losses"] >= config.MAX_DAILY_LOSSES:
            return False, f"🚫 Max {config.MAX_DAILY_LOSSES} pertes/jour"

        return True, "✅ OK"

    def add(self, signal):
        self.state["active_signals"].append(signal)
        self.state["last_signal_time_utc"][signal["pair"]] = now_utc().isoformat()
        self._save()

    def update(self, sid, updates):
        for sig in self.state["active_signals"]:
            if sig["id"] == sid:
                sig.update(updates)
                self._save()
                return True
        return False

    def close(self, sid, result, pips):
        for sig in self.state["active_signals"]:
            if sig["id"] == sid:
                sig["status"] = "CLOSED"
                sig["result"] = result
                sig["pips"] = pips
                sig["closed_at_utc"] = now_utc().isoformat()

                if result == "SL":
                    self.state["daily_losses"] += 1
                    self.state["consecutive_sl"] += 1
                    self.state["daily_stats"]["losses"] += 1
                    self.state["daily_stats"]["pips"] += pips

                    if self.state["consecutive_sl"] >= config.PAUSE_AFTER_CONSECUTIVE_SL:
                        from datetime import timedelta
                        pause = now_utc() + timedelta(minutes=30)
                        self.state["paused_until_utc"] = pause.isoformat()
                        logger.warning(f"🛑 PAUSE: {config.PAUSE_AFTER_CONSECUTIVE_SL} SL")
                else:
                    self.state["consecutive_sl"] = 0
                    self.state["daily_stats"]["wins"] += 1
                    self.state["daily_stats"]["pips"] += max(0, pips)

                self._save()
                return sig
        return None

    def active(self):
        return [s for s in self.state["active_signals"] if s["status"] == "ACTIVE"]

    def stats(self):
        closed = [s for s in self.state["active_signals"] if s["status"] == "CLOSED"]
        if not closed:
            return {"total": 0, "win_rate": 0, "avg_pips": 0, "total_pips": 0}
        wins = len([s for s in closed if s["result"] in ["TP1", "TP2", "BE"]])
        total_pips = sum(s.get("pips", 0) for s in closed)
        return {
            "total": len(closed),
            "wins": wins,
            "losses": len(closed) - wins,
            "win_rate": round(wins / len(closed) * 100, 1),
            "avg_pips": round(total_pips / len(closed), 2),
            "total_pips": round(total_pips, 2),
            "daily": self.state["daily_stats"],
            "consecutive_sl": self.state["consecutive_sl"],
        }

risk_manager = RiskManagerV2()
