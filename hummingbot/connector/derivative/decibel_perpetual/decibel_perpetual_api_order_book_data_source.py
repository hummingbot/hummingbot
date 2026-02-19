import asyncio
import time
from typing import Any, Dict, List, Optional
import httpx

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.connector.derivative.decibel_perpetual.decibel_utils import TRADING_HTTP_URL, TRADING_WS_URL

class DecibelPerpetualAPIOrderBookDataSource:
    """
    Decibel Order Book Data Source.
    Fetches snapshots via REST and real-time updates via WebSocket.
    """
    def __init__(self, trading_pairs: List[str]):
        self._trading_pairs = trading_pairs
        self._market_map: Dict[str, str] = {} # trading_pair -> market_addr
        self._snapshot_msg_queue = asyncio.Queue()

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """
        Pulls last prices from /api/v1/markets.
        Note: Decibel SDK indicates that market data is in the markets list.
        """
        results = {}
        async with httpx.AsyncClient() as client:
            # We assume the API key will be injected via headers in the future
            # For now, following the path logic from the SDK
            url = f"{TRADING_HTTP_URL}/api/v1/markets"
            response = await client.get(url)
            if response.status_code == 200:
                markets = response.json()
                for m in markets:
                    pair = m["market_name"]
                    if pair in trading_pairs:
                        # Decibel might provide index_price or mark_price
                        # We'll use a placeholder for now until we see the real JSON schema
                        results[pair] = float(m.get("index_price", 0.0))
        return results

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Fetches a full L2 snapshot from /api/v1/depth.
        """
        market_addr = await self._get_market_addr(trading_pair)
        async with httpx.AsyncClient() as client:
            url = f"{TRADING_HTTP_URL}/api/v1/depth"
            params = {"market": market_addr, "limit": 100}
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # data structure from SDK: { bids: [{price, size}], asks: [...], unix_ms }
                return self.deserialize_snapshot(data, trading_pair)
            else:
                raise Exception(f"Failed to fetch order book for {trading_pair}: {response.text}")

    def deserialize_snapshot(self, data: Dict[str, Any], trading_pair: str) -> OrderBook:
        """
        Converts Decibel JSON snapshot into Hummingbot OrderBook object.
        """
        # Hummingbot expects specific message format
        timestamp = data["unix_ms"] * 1e-3
        book = OrderBook()
        
        bids = [(float(obj["price"]), float(obj["size"])) for obj in data["bids"]]
        asks = [(float(obj["price"]), float(obj["size"])) for obj in data["asks"]]
        
        msg = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(data["unix_ms"]),
                "bids": bids,
                "asks": asks
            },
            timestamp=timestamp
        )
        book.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return book

    async def _get_market_addr(self, trading_pair: str) -> str:
        """Helper to resolve pair name to Aptos address."""
        if not self._market_map:
            async with httpx.AsyncClient() as client:
                url = f"{TRADING_HTTP_URL}/api/v1/markets"
                r = await client.get(url)
                if r.status_code == 200:
                    for m in r.json():
                        self._market_map[m["market_name"]] = m["market_addr"]
        
        return self._market_map.get(trading_pair, "")

# Placeholder for WS logic until we have the API key to test connectivity
