"""Telegram Bot V2 Hybrid — Messages avec score qualité."""
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from utils import logger
from config import config

class TelegramBotV2:
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.channel_id = config.TELEGRAM_CHANNEL_ID

    def _metal_emoji(self, pair):
        if "XAU" in pair: return "🥇"
        if "XAG" in pair: return "🥈"
        if "BTC" in pair: return "₿"
        if "ETH" in pair: return "Ξ"
        return "📊"

    def _score_emoji(self, score):
        if score >= 80: return "🔥"
        if score >= 65: return "✨"
        if score >= 55: return "⭐"
        return "⚡"

    async def send_signal(self, signal):
        emoji_dir = "🟢 BUY" if signal["direction"] == "LONG" else "🔴 SELL"
        metal = self._metal_emoji(signal["pair"])
        score = signal.get("_score", 50)
        score_emoji = self._score_emoji(score)

        message = f"""{metal} {score_emoji} 🚨 {signal['pair']} | {emoji_dir}

💰 {signal['entry']} | 🛑 {signal['sl']}
✅ TP1: {signal['tp1']} | TP2: {signal['tp2']}
📊 R:R 1:{signal['rr']} | Conf: {signal['confidence']}%

🎯 Score Qualité: <b>{score}/100</b>
📡 Binance Futures

⏱️ 5 min | Quota: 3/h
"""
        await self._send(message)

    async def send_message(self, text):
        await self._send(text)

    async def send_pause_alert(self, until):
        msg = f"🛑 PAUSE — {config.PAUSE_AFTER_CONSECUTIVE_SL} SL\n⏸️ Jusqu'à {until}"
        await self._send(msg)

    async def send_daily_stats(self, stats):
        emoji = "🟢" if stats["win_rate"] >= 50 else "🔴"
        msg = f"""📊 STATS

{emoji} WR: {stats['win_rate']}% | ✅ {stats.get('wins',0)} | ❌ {stats.get('losses',0)}
📈 {stats.get('total_pips',0)} pts | Moy: {stats.get('avg_pips',0)}
"""
        await self._send(msg)

    async def _send(self, text):
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Telegram: {e}")

telegram_bot = TelegramBotV2()
