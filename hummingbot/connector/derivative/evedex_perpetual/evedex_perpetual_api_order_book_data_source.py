import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class EvedexPerpetualAPIOrderBookDataSource:
    """
    Order book data source for EVEDEX perpetual futures.

    Uses:
    - REST GET /api/market/{instrument}/deep for snapshots
    - Centrifuge WebSocket (wss://ws.evedex.com) for streaming updates
      Channels: orderBook-{instrument}-0.1, trade-{instrument}
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._message_queue: Dict[str, asyncio.Queue] = {
            "diff": asyncio.Queue(),
            "trade": asyncio.Queue(),
            "snapshot": asyncio.Queue(),
        }

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            import logging
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        import aiohttp
        result = {}
        base_url = web_utils.get_trade_base_url(domain or self._domain)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                instruments = await resp.json()

        for instr in instruments:
            instrument_id = instr.get("id", "")
            trading_pair = web_utils.instrument_to_trading_pair(instrument_id)
            if trading_pair in trading_pairs:
                last_price = instr.get("lastPrice") or instr.get("markPrice") or 0
                result[trading_pair] = float(last_price)

        return result

    async def get_snapshot(self, trading_pair: str, depth: int = 50) -> Dict[str, Any]:
        import aiohttp
        instrument_id = web_utils.trading_pair_to_instrument(trading_pair)
        base_url = web_utils.get_trade_base_url(self._domain)
        url = f"{base_url}/api/market/{instrument_id}/deep"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"maxLevel": depth},
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                return data

    async def get_new_order_book_message(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self.get_snapshot(trading_pair)
        timestamp = time.time()

        # EVEDEX order book format: {bids: [[price, quantity], ...], asks: [[price, quantity], ...]}
        raw_bids = snapshot.get("bids", [])
        raw_asks = snapshot.get("asks", [])

        bids = [[float(b[0]), float(b[1])] for b in raw_bids if len(b) >= 2]
        asks = [[float(a[0]), float(a[1])] for a in raw_asks if len(a) >= 2]

        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )

    async def listen_for_subscriptions(self):
        """Connect to Centrifuge WebSocket and subscribe to order book channels."""
        ws_url = web_utils.get_ws_url(self._domain)
        prefix = web_utils.get_ws_prefix(self._domain)

        while True:
            try:
                import websockets
                async with websockets.connect(ws_url) as ws:
                    # Centrifuge handshake
                    connect_msg = {"id": 1, "connect": {"token": "", "data": {}}}
                    await ws.send(json.dumps(connect_msg))
                    response = await asyncio.wait_for(ws.recv(), timeout=10)

                    # Subscribe to order book and trade channels for each pair
                    msg_id = 2
                    for trading_pair in self._trading_pairs:
                        instrument_id = web_utils.trading_pair_to_instrument(trading_pair)

                        # Subscribe to order book
                        ob_channel = f"{prefix}:orderBook-{instrument_id}-0.1"
                        await ws.send(json.dumps({
                            "id": msg_id,
                            "subscribe": {"channel": ob_channel},
                        }))
                        msg_id += 1

                        # Subscribe to trades
                        trade_channel = f"{prefix}:trade-{instrument_id}"
                        await ws.send(json.dumps({
                            "id": msg_id,
                            "subscribe": {"channel": trade_channel},
                        }))
                        msg_id += 1

                    # Process incoming messages
                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            await self._process_ws_message(msg, prefix)
                        except Exception as e:
                            self.logger().debug(f"WS message parse error: {e}")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Order book WS error: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _process_ws_message(self, msg: Dict[str, Any], prefix: str):
        """Route Centrifuge publication to appropriate queue."""
        # Centrifuge push format: {"push": {"channel": "...", "pub": {"data": {...}}}}
        push = msg.get("push", {})
        channel = push.get("channel", "")
        pub = push.get("pub", {})
        data = pub.get("data", {})

        if not channel or not data:
            return

        # Remove prefix
        channel_name = channel.replace(f"{prefix}:", "")

        if "orderBook-" in channel_name and "-best" not in channel_name:
            # Order book update
            instrument_id = channel_name.replace("orderBook-", "").rsplit("-", 1)[0]
            trading_pair = web_utils.instrument_to_trading_pair(instrument_id)
            instrument_data = data.get("orderBook", data)
            bids = [[float(b[0]), float(b[1])] for b in instrument_data.get("bids", []) if len(b) >= 2]
            asks = [[float(a[0]), float(a[1])] for a in instrument_data.get("asks", []) if len(a) >= 2]

            msg_obj = OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content={
                    "trading_pair": trading_pair,
                    "update_id": int(time.time() * 1000),
                    "bids": bids,
                    "asks": asks,
                },
                timestamp=time.time(),
            )
            await self._message_queue["diff"].put(msg_obj)

        elif "trade-" in channel_name and "recent" not in channel_name:
            # Trade event
            instrument_id = channel_name.replace("trade-", "")
            trading_pair = web_utils.instrument_to_trading_pair(instrument_id)
            side = data.get("side", "buy")

            trade_msg = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content={
                    "trading_pair": trading_pair,
                    "trade_type": 1.0 if side == "buy" else 2.0,
                    "trade_id": data.get("executionId", str(time.time())),
                    "update_id": int(time.time() * 1000),
                    "price": float(data.get("fillPrice", 0)),
                    "amount": float(data.get("fillQuantity", 0)),
                },
                timestamp=time.time(),
            )
            await self._message_queue["trade"].put(trade_msg)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                msg = await asyncio.wait_for(self._message_queue["diff"].get(), timeout=1.0)
                await output.put(msg)
            except asyncio.TimeoutError:
                pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            for trading_pair in self._trading_pairs:
                try:
                    snapshot = await self.get_new_order_book_message(trading_pair)
                    await output.put(snapshot)
                except Exception as e:
                    self.logger().error(f"Snapshot error for {trading_pair}: {e}")
            await asyncio.sleep(60.0)

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                msg = await asyncio.wait_for(self._message_queue["trade"].get(), timeout=1.0)
                await output.put(msg)
            except asyncio.TimeoutError:
                pass
