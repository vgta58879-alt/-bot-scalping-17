"""Webhook Sender — Push HTTP rapide (<100ms) + fallback Telegram.

Architecture:
1. Envoi webhook PRIORITAIRE vers l'URL configurée
2. Si webhook échoue (timeout 3s) → fallback Telegram
3. Retry automatique x2 sur échec webhook
"""
import asyncio
import aiohttp
from datetime import datetime, timezone
from config import config
from utils import logger
from telegram_bot_v2 import telegram_bot

class WebhookSender:
    """
    Envoie les signaux via webhook HTTP POST.

    Configuration .env:
    WEBHOOK_URL=https://ton-app.com/webhook  (ton serveur/app)
    WEBHOOK_SECRET=webhook_secret_key        (signature HMAC)
    WEBHOOK_TIMEOUT=3                        (secondes)
    """

    def __init__(self):
        self.webhook_url = getattr(config, 'WEBHOOK_URL', '')
        self.webhook_secret = getattr(config, 'WEBHOOK_SECRET', '')
        self.timeout = getattr(config, 'WEBHOOK_TIMEOUT', 3)
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _build_payload(self, signal, signal_type="SIGNAL"):
        """Construit le payload JSON du webhook."""
        return {
            "type": signal_type,  # "SIGNAL", "PRE_SIGNAL", "UPDATE", "CLOSE", "BE"
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "pair": signal.get("pair", ""),
            "direction": signal.get("direction", ""),
            "strategy": signal.get("strategy", ""),
            "entry": signal.get("entry", 0),
            "sl": signal.get("sl", 0),
            "tp1": signal.get("tp1", 0),
            "tp2": signal.get("tp2", 0),
            "rr": signal.get("rr", 0),
            "confidence": signal.get("confidence", 0),
            "score": signal.get("_score", 0),
            "market_direction": signal.get("market_direction", ""),
            "current_price": signal.get("current_price", signal.get("entry", 0)),
            "pips": signal.get("pips", 0),
            "result": signal.get("result", ""),
            "id": signal.get("id", ""),
        }

    async def send_webhook(self, signal, signal_type="SIGNAL"):
        """
        Envoie le webhook avec retry.
        Returns: (success: bool, error: str)
        """
        if not self.webhook_url:
            return False, "WEBHOOK_URL non configuré"

        payload = self._build_payload(signal, signal_type)
        headers = {
            "Content-Type": "application/json",
            "X-Signal-Bot": "scalping-v2",
        }

        # Signature HMAC si secret configuré
        if self.webhook_secret:
            import hmac, hashlib, json as json_mod
            body = json_mod.dumps(payload, sort_keys=True)
            sig = hmac.new(
                self.webhook_secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Signature"] = sig

        session = await self._get_session()

        for attempt in range(1, 3):  # 2 tentatives
            try:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status in [200, 201, 202]:
                        logger.info(f"✅ Webhook envoyé ({signal_type}) — HTTP {resp.status}")
                        return True, ""
                    else:
                        body = await resp.text()
                        logger.warning(f"⚠️ Webhook HTTP {resp.status}: {body[:100]}")
                        if attempt == 1:
                            await asyncio.sleep(1)
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Webhook timeout (tentative {attempt})")
                if attempt == 1:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Webhook erreur: {e}")
                if attempt == 1:
                    await asyncio.sleep(1)

        return False, "Webhook échoué après 2 tentatives"

    async def send(self, signal, signal_type="SIGNAL"):
        """
        Envoie webhook PRIORITAIRE + fallback Telegram.
        """
        # 1. Essayer webhook
        webhook_ok, webhook_err = await self.send_webhook(signal, signal_type)

        if webhook_ok:
            # Webhook OK → pas besoin de Telegram (sauf pour CLOSE/BE)
            if signal_type in ["CLOSE", "BE", "UPDATE"]:
                await telegram_bot.send_message(self._format_telegram(signal, signal_type))
            return True

        # 2. Fallback Telegram
        logger.warning(f"🔄 Fallback Telegram — {webhook_err}")
        if signal_type == "SIGNAL":
            await telegram_bot.send_signal(signal)
        elif signal_type == "PRE_SIGNAL":
            await telegram_bot.send_message(self._format_pre_signal(signal))
        elif signal_type == "CLOSE":
            await telegram_bot.send_message(self._format_close(signal))
        elif signal_type == "BE":
            await telegram_bot.send_message(self._format_be(signal))
        elif signal_type == "UPDATE":
            await telegram_bot.send_message(self._format_update(signal))

        return True

    def _format_telegram(self, signal, sig_type):
        """Format fallback Telegram si webhook OK."""
        if sig_type == "CLOSE":
            return f"📊 {signal.get('pair')} {signal.get('result')} | {signal.get('pips', 0):+.2f} pts"
        elif sig_type == "BE":
            return f"🔒 {signal.get('pair')} TP1 → BE"
        return ""

    def _format_pre_signal(self, signal):
        metal = "🥇" if "XAU" in signal.get("pair", "") else ""
        emoji = "🟡" if signal.get("direction") == "LONG" else "🟠"
        return f"""{emoji} {metal} ⚡ PRE-SIGNAL — {signal['pair']}

Direction probable: <b>{signal['direction']}</b>
Prix actuel: <code>{signal.get('current_price', 'N/A')}</code>
Confiance: {signal.get('confidence', 0)}%

⏳ Attendre la clôture M5 pour confirmation...
<i>Ne pas entrer sur ce pre-signal</i>
"""

    def _format_close(self, signal):
        emoji = "🟢" if signal.get("result") in ["TP1", "TP2", "BE"] else "🔴"
        return f"{emoji} {signal.get('pair')} {signal.get('result')} | {signal.get('pips', 0):+.2f} pts"

    def _format_be(self, signal):
        return f"🔒 {signal.get('pair')} SL → BE | TP2: {signal.get('tp2')}"

    def _format_update(self, signal):
        pips = signal.get("pips", 0)
        emoji = "🟢" if pips > 0 else "🔴"
        return f"{emoji} {signal.get('pair')} | {pips:+.2f} pts"

webhook_sender = WebhookSender()
