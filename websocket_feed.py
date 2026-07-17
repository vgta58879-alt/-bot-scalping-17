"""WebSocket Binance — données tick-by-tick en temps réel."""
import asyncio, json
import websockets
from config import config
from utils import logger

class WebSocketFeed:
    """
    Connexion WebSocket persistante à Binance Futures.
    Reçoit les prix en temps réel pour le suivi des trades.
    """

    def __init__(self):
        self.ws_url = config.BINANCE_WS_URL
        self.price_cache = {}  # {symbol: current_price}
        self.running = False
        self.ws = None

    def get_price(self, symbol):
        """Retourne le dernier prix connu."""
        return self.price_cache.get(symbol.upper())

    async def connect(self):
        """Connexion WebSocket persistante avec reconnexion auto."""
        self.running = True
        streams = "/".join([f"{s.lower()}@aggTrade" for s in config.PAIRS])
        url = f"{self.ws_url}/{streams}"

        while self.running:
            try:
                logger.info(f"🌐 Connexion WebSocket: {len(config.PAIRS)} paires")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self.ws = ws
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(json.loads(message))
            except Exception as e:
                logger.error(f"WebSocket erreur: {e}")
                logger.info("🔄 Reconnexion dans 5s...")
                await asyncio.sleep(5)

    async def _handle_message(self, data):
        """Traite un message aggTrade."""
        symbol = data.get("s", "").upper()
        price = float(data.get("p", 0))
        if symbol and price > 0:
            self.price_cache[symbol] = price

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()

ws_feed = WebSocketFeed()
