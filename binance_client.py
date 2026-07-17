"""Client Binance Futures — données temps réel via REST + WebSocket."""
import asyncio, json, aiohttp
import pandas as pd
from datetime import datetime, timezone
from config import config
from utils import logger, binance_signature

class BinanceClient:
    """
    Connexion à Binance Futures pour:
    - Données klines (candles) en temps réel
    - Prix actuel (ticker)
    - Volume 24h
    - WebSocket pour tick-by-tick
    """

    def __init__(self):
        self.base_url = config.BINANCE_BASE_URL
        self.api_key = config.BINANCE_API_KEY
        self.secret = config.BINANCE_SECRET_KEY
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_klines(self, symbol, interval="5m", limit=100):
        """
        Récupère les candles OHLCV depuis Binance Futures.
        Latence: ~100-300ms. Pas besoin de clé API.
        """
        url = f"{self.base_url}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        try:
            session = await self._get_session()
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    df = pd.DataFrame(data, columns=[
                        "open_time", "Open", "High", "Low", "Close", "Volume",
                        "close_time", "quote_volume", "trades", "taker_buy_base",
                        "taker_buy_quote", "ignore"
                    ])
                    # Conversion types
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                    df.set_index("open_time", inplace=True)
                    logger.info(f"📊 Klines {symbol} {interval}: {len(df)} candles")
                    return df
                else:
                    logger.error(f"Erreur klines {symbol}: HTTP {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Exception klines {symbol}: {e}")
            return None

    async def get_multi_timeframe(self, symbol):
        """Récupère M5, M15, H1 en parallèle."""
        tasks = [
            self.get_klines(symbol, config.TF_ENTRY, 100),
            self.get_klines(symbol, config.TF_CONFIRM, 50),
            self.get_klines(symbol, config.TF_TREND, 50),
        ]
        entry, confirm, trend = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrer les exceptions
        entry = entry if not isinstance(entry, Exception) else None
        confirm = confirm if not isinstance(confirm, Exception) else None
        trend = trend if not isinstance(trend, Exception) else None

        return {"entry": entry, "confirm": confirm, "trend": trend}

    async def get_ticker_price(self, symbol):
        """Prix actuel en temps réel (REST)."""
        url = f"{self.base_url}/fapi/v1/ticker/price"
        try:
            session = await self._get_session()
            async with session.get(url, params={"symbol": symbol}, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data["price"])
        except Exception as e:
            logger.error(f"Erreur ticker {symbol}: {e}")
        return None

    async def get_24h_stats(self, symbol):
        """Volume et variation 24h."""
        url = f"{self.base_url}/fapi/v1/ticker/24hr"
        try:
            session = await self._get_session()
            async with session.get(url, params={"symbol": symbol}, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Erreur 24h {symbol}: {e}")
        return None

binance_client = BinanceClient()
