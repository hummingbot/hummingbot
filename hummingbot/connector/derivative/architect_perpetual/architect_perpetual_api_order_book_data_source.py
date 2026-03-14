import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class ArchitectPerpetualAPIOrderBookDataSource:
    """
    Order book data source for Architect perpetual futures.

    Uses the architect-py SDK for all data access:
    - REST-like: get_l2_book_snapshot() for snapshots
    - Streaming: stream_l2_book_updates() for diffs, stream_trades() for trades
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
        result = {}
        client = self._connector._client
        if client is None:
            return result
        venue = self._connector._execution_venue
        for trading_pair in trading_pairs:
            symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, venue)
            try:
                ticker = await client.get_ticker(symbol=symbol, venue=venue)
                # Ticker field 'p' = last_price, 'mp' = mark_price
                price = float(ticker.p or ticker.mp or 0)
                result[trading_pair] = price
            except Exception as e:
                self.logger().debug(f"Failed to get ticker for {trading_pair}: {e}")
        return result

    async def get_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        client = self._connector._client
        if client is None:
            return {}
        venue = self._connector._execution_venue
        symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, venue)
        try:
            snap = await client.get_l2_book_snapshot(symbol=symbol, venue=venue)
            bids = [[float(level.p), float(level.q)] for level in (snap.b or [])]
            asks = [[float(level.p), float(level.q)] for level in (snap.a or [])]
            return {
                "bids": bids,
                "asks": asks,
                "sequence_number": snap.sn,
            }
        except Exception as e:
            self.logger().warning(f"Snapshot failed for {trading_pair}: {e}")
            return {}

    async def get_new_order_book_message(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self.get_snapshot(trading_pair)
        timestamp = time.time()
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": snapshot.get("sequence_number", int(timestamp * 1000)),
                "bids": snapshot.get("bids", []),
                "asks": snapshot.get("asks", []),
            },
            timestamp=timestamp,
        )

    async def listen_for_subscriptions(self):
        """Subscribe to L2 book updates and trade streams for all trading pairs."""
        while True:
            try:
                await self._run_subscriptions()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Order book subscription error: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _run_subscriptions(self):
        client = self._connector._client
        if client is None:
            await asyncio.sleep(5)
            return
        venue = self._connector._execution_venue
        tasks = []
        for trading_pair in self._trading_pairs:
            symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, venue)
            tasks.append(self._stream_l2_updates(symbol, trading_pair, venue))
            tasks.append(self._stream_trades(symbol, trading_pair, venue))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _stream_l2_updates(self, symbol: str, trading_pair: str, venue: str):
        client = self._connector._client
        try:
            async for update in client.stream_l2_book_updates(symbol=symbol, venue=venue):
                from architect_py.grpc.models.Marketdata.L2BookUpdate import L2BookSnapshot, L2BookDiff
                timestamp = time.time()

                if hasattr(update, 'b') and hasattr(update, 'a') and hasattr(update, 'sn'):
                    # Full snapshot
                    bids = [[float(l.p), float(l.q)] for l in (update.b or [])]
                    asks = [[float(l.p), float(l.q)] for l in (update.a or [])]
                    msg = OrderBookMessage(
                        message_type=OrderBookMessageType.SNAPSHOT,
                        content={
                            "trading_pair": trading_pair,
                            "update_id": update.sn,
                            "bids": bids,
                            "asks": asks,
                        },
                        timestamp=timestamp,
                    )
                    await self._message_queue["snapshot"].put(msg)
                elif hasattr(update, 'bids') or hasattr(update, 'asks'):
                    # Diff update
                    bids = [[float(l.p), float(l.q)] for l in (getattr(update, 'bids', None) or [])]
                    asks = [[float(l.p), float(l.q)] for l in (getattr(update, 'asks', None) or [])]
                    sn = getattr(update, 'sn', int(timestamp * 1000))
                    msg = OrderBookMessage(
                        message_type=OrderBookMessageType.DIFF,
                        content={
                            "trading_pair": trading_pair,
                            "update_id": sn,
                            "bids": bids,
                            "asks": asks,
                        },
                        timestamp=timestamp,
                    )
                    await self._message_queue["diff"].put(msg)
                else:
                    # Try to treat as snapshot or diff based on available fields
                    raw_bids = getattr(update, 'b', None) or getattr(update, 'bids', None) or []
                    raw_asks = getattr(update, 'a', None) or getattr(update, 'asks', None) or []
                    sn = getattr(update, 'sn', int(timestamp * 1000))
                    bids = [[float(l.p), float(l.q)] for l in raw_bids]
                    asks = [[float(l.p), float(l.q)] for l in raw_asks]
                    msg = OrderBookMessage(
                        message_type=OrderBookMessageType.DIFF,
                        content={
                            "trading_pair": trading_pair,
                            "update_id": sn,
                            "bids": bids,
                            "asks": asks,
                        },
                        timestamp=timestamp,
                    )
                    await self._message_queue["diff"].put(msg)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().warning(f"L2 stream error for {symbol}: {e}")
            raise

    async def _stream_trades(self, symbol: str, trading_pair: str, venue: str):
        client = self._connector._client
        try:
            async for trade in client.stream_trades(symbol=symbol, venue=venue):
                from architect_py.common_types.order_dir import OrderDir
                timestamp = time.time()
                trade_type = 1.0 if trade.d == OrderDir.BUY else 2.0
                msg = OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content={
                        "trading_pair": trading_pair,
                        "trade_type": trade_type,
                        "trade_id": str(int(timestamp * 1e9)),
                        "update_id": int(timestamp * 1000),
                        "price": float(trade.p),
                        "amount": float(trade.q),
                    },
                    timestamp=timestamp,
                )
                await self._message_queue["trade"].put(msg)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().warning(f"Trade stream error for {symbol}: {e}")
            raise

    async def listen_for_order_book_diffs(self, ev_loop, output: asyncio.Queue):
        while True:
            try:
                msg = await asyncio.wait_for(self._message_queue["diff"].get(), timeout=1.0)
                await output.put(msg)
            except asyncio.TimeoutError:
                pass

    async def listen_for_order_book_snapshots(self, ev_loop, output: asyncio.Queue):
        while True:
            # First try snapshot queue from WebSocket
            try:
                msg = await asyncio.wait_for(self._message_queue["snapshot"].get(), timeout=0.1)
                await output.put(msg)
                continue
            except asyncio.TimeoutError:
                pass
            # Periodic REST snapshots as fallback
            for trading_pair in self._trading_pairs:
                try:
                    snapshot = await self.get_new_order_book_message(trading_pair)
                    await output.put(snapshot)
                except Exception as e:
                    self.logger().error(f"Snapshot error for {trading_pair}: {e}")
            await asyncio.sleep(60.0)

    async def listen_for_trades(self, ev_loop, output: asyncio.Queue):
        while True:
            try:
                msg = await asyncio.wait_for(self._message_queue["trade"].get(), timeout=1.0)
                await output.put(msg)
            except asyncio.TimeoutError:
                pass
