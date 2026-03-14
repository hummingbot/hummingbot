import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.connector.exchange.abstract_exchange_api_order_book_data_source import (
    AbstractExchangeAPIOrderBookDataSource,
)
from hummingbot.logger import HummingbotLogger


class GrvtPerpetualAPIOrderBookDataSource(AbstractExchangeAPIOrderBookDataSource):
    """
    Provides order book data for GRVT perpetual markets.
    Handles both REST snapshots (for initialization) and WebSocket streaming.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = {}

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        """Fetch last traded prices for a list of trading pairs."""
        import aiohttp
        result = {}
        base_url = web_utils.get_market_data_url(domain or self._domain)

        async with aiohttp.ClientSession() as session:
            for trading_pair in trading_pairs:
                instrument = web_utils.trading_pair_to_instrument(trading_pair)
                try:
                    async with session.post(
                        f"{base_url}{CONSTANTS.TICKER_URL}",
                        json={"instrument": instrument},
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        data = await resp.json()
                        ticker = data.get("result", {})
                        last_price = ticker.get("last_price") or ticker.get("mark_price")
                        if last_price:
                            result[trading_pair] = float(last_price)
                except Exception:
                    pass
        return result

    async def get_snapshot(self, trading_pair: str, limit: int = 1000) -> Dict[str, Any]:
        """Fetch order book snapshot via REST."""
        import aiohttp
        instrument = web_utils.trading_pair_to_instrument(trading_pair)
        base_url = web_utils.get_market_data_url(self._domain)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}{CONSTANTS.ORDERBOOK_URL}",
                json={"instrument": instrument, "depth": min(limit, CONSTANTS.ORDERBOOK_DEFAULT_DEPTH)},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                return data.get("result", {})

    async def get_new_order_book_message(self, trading_pair: str) -> OrderBookMessage:
        """Create an order book snapshot message."""
        snapshot = await self.get_snapshot(trading_pair)
        snapshot_timestamp = time.time()

        bids = [
            OrderBookRow(float(bid["price"]), float(bid["size"]), 0)
            for bid in snapshot.get("bids", [])
        ]
        asks = [
            OrderBookRow(float(ask["price"]), float(ask["size"]), 0)
            for ask in snapshot.get("asks", [])
        ]

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": int(snapshot_timestamp * 1000),
            "bids": [[b.price, b.amount] for b in bids],
            "asks": [[a.price, a.amount] for a in asks],
        }
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=order_book_message_content,
            timestamp=snapshot_timestamp,
        )

    async def listen_for_subscriptions(self):
        """Subscribe to WebSocket order book updates."""
        ws_url = web_utils.get_market_ws_url(self._domain)
        while True:
            try:
                import websockets
                async with websockets.connect(ws_url) as ws:
                    # Subscribe to order book streams for each trading pair
                    for trading_pair in self._trading_pairs:
                        instrument = web_utils.trading_pair_to_instrument(trading_pair)
                        sub_msg = {
                            "jsonrpc": "2.0",
                            "method": "subscribe",
                            "params": {
                                "stream": CONSTANTS.WS_ORDERBOOK_STREAM,
                                "selectors": [instrument],
                            },
                            "id": 1,
                        }
                        await ws.send(str(sub_msg).replace("'", '"'))

                    async for raw_msg in ws:
                        msg = eval(raw_msg) if isinstance(raw_msg, str) else raw_msg
                        await self._process_websocket_message(msg)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Order book WebSocket error: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _process_websocket_message(self, msg: Dict[str, Any]):
        """Process incoming WebSocket message and route to appropriate queue."""
        # Handle order book updates
        if "result" in msg and "instrument" in msg.get("result", {}):
            result = msg["result"]
            instrument = result.get("instrument", "")
            trading_pair = web_utils.instrument_to_trading_pair(instrument)

            if trading_pair in self._trading_pairs:
                queue_key = self._get_trading_pair_diff_update_queue_key(trading_pair)
                if queue_key not in self._message_queue:
                    self._message_queue[queue_key] = asyncio.Queue()
                await self._message_queue[queue_key].put(result)

    def _get_trading_pair_diff_update_queue_key(self, trading_pair: str) -> str:
        return f"diff:{trading_pair}"

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Listen for incremental order book updates."""
        while True:
            for trading_pair in self._trading_pairs:
                queue_key = self._get_trading_pair_diff_update_queue_key(trading_pair)
                if queue_key in self._message_queue:
                    try:
                        msg = self._message_queue[queue_key].get_nowait()
                        # Parse and emit order book diff message
                        bids = [[float(b["price"]), float(b["size"])] for b in msg.get("bids", [])]
                        asks = [[float(a["price"]), float(a["size"])] for a in msg.get("asks", [])]
                        order_book_message = OrderBookMessage(
                            message_type=OrderBookMessageType.DIFF,
                            content={
                                "trading_pair": trading_pair,
                                "update_id": int(time.time() * 1000),
                                "bids": bids,
                                "asks": asks,
                            },
                            timestamp=time.time(),
                        )
                        await output.put(order_book_message)
                    except asyncio.QueueEmpty:
                        pass
            await asyncio.sleep(0.1)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Periodically fetch and emit full order book snapshots."""
        while True:
            for trading_pair in self._trading_pairs:
                try:
                    snapshot_msg = await self.get_new_order_book_message(trading_pair)
                    await output.put(snapshot_msg)
                except Exception as e:
                    self.logger().error(f"Snapshot error for {trading_pair}: {e}")
            await asyncio.sleep(60.0)

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Subscribe to recent trade streams."""
        ws_url = web_utils.get_market_ws_url(self._domain)
        while True:
            try:
                import websockets
                async with websockets.connect(ws_url) as ws:
                    for trading_pair in self._trading_pairs:
                        instrument = web_utils.trading_pair_to_instrument(trading_pair)
                        sub_msg = {
                            "jsonrpc": "2.0",
                            "method": "subscribe",
                            "params": {
                                "stream": CONSTANTS.WS_TRADES_STREAM,
                                "selectors": [instrument],
                            },
                            "id": 2,
                        }
                        import json
                        await ws.send(json.dumps(sub_msg))

                    async for raw_msg in ws:
                        import json
                        try:
                            msg = json.loads(raw_msg)
                        except Exception:
                            continue

                        result = msg.get("result", {})
                        if "trade" not in result:
                            continue

                        trade = result["trade"]
                        instrument = result.get("instrument", "")
                        trading_pair = web_utils.instrument_to_trading_pair(instrument)

                        trade_message = OrderBookMessage(
                            message_type=OrderBookMessageType.TRADE,
                            content={
                                "trading_pair": trading_pair,
                                "trade_type": 1.0 if trade.get("is_taker_buyer") else 2.0,
                                "trade_id": trade.get("trade_id", ""),
                                "update_id": int(time.time() * 1000),
                                "price": float(trade.get("price", 0)),
                                "amount": float(trade.get("size", 0)),
                            },
                            timestamp=float(trade.get("event_time", time.time() * 1e9)) / 1e9,
                        )
                        await output.put(trade_message)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Trades WebSocket error: {e}", exc_info=True)
                await asyncio.sleep(5.0)
