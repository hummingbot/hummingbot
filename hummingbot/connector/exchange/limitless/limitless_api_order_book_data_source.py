"""Order book data source that delegates to the inner LimitlessConnector's WS."""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.limitless import limitless_constants as CONSTANTS
from hummingbot.connector.exchange.limitless.limitless_order_book import LimitlessOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.limitless.limitless_exchange import LimitlessExchange


class LimitlessAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    POLL_INTERVAL = 2.0  # seconds between orderbook polls from inner connector

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LimitlessExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """Fetch orderbook snapshot via inner connector."""
        inner = self._connector._inner_connector
        slug = self._connector._trading_pair_to_slug(trading_pair)
        # Skip if slug is still the placeholder (real slug not yet registered)
        if slug == trading_pair:
            raise ValueError(f"No real slug registered yet for {trading_pair}")
        ob = await inner.get_order_book(slug)
        return {
            "trading_pair": trading_pair,
            "bids": [[b["price"], b["size"]] for b in ob.get("bids", [])],
            "asks": [[a["price"], a["size"]] for a in ob.get("asks", [])],
            "time": time.time(),
        }

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        timestamp = snapshot["time"]
        snapshot_msg = LimitlessOrderBook.snapshot_message_from_exchange(
            snapshot, timestamp, metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Not used — we poll the inner connector's cached orderbooks instead."""
        raise NotImplementedError("LimitlessAPIOrderBookDataSource uses polling, not direct WS")

    async def _subscribe_channels(self, ws: WSAssistant):
        """Not used — inner connector handles WS subscriptions."""
        pass

    async def listen_for_subscriptions(self):
        """Override the parent's WS-based listener with a polling loop.

        The inner LimitlessConnector already maintains a WS connection and
        caches orderbook snapshots. We poll those cached values and push
        them as snapshot messages into the diff queue.
        """
        while True:
            try:
                inner = self._connector._inner_connector
                if inner is None:
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue

                cached = inner.cached_orderbooks() if callable(inner.cached_orderbooks) else inner.cached_orderbooks
                for trading_pair in self._trading_pairs:
                    slug = self._connector._trading_pair_to_slug(trading_pair)
                    if not slug or slug not in cached:
                        continue

                    ob = cached[slug]
                    msg_data = {
                        "trading_pair": trading_pair,
                        "bids": [[b["price"], b["size"]] for b in ob.get("bids", [])],
                        "asks": [[a["price"], a["size"]] for a in ob.get("asks", [])],
                    }
                    timestamp = time.time()
                    snapshot_msg = LimitlessOrderBook.snapshot_message_from_exchange(
                        msg_data, timestamp, {"trading_pair": trading_pair}
                    )
                    self._message_queue[self._diff_messages_queue_key].put_nowait(snapshot_msg)

                await asyncio.sleep(self.POLL_INTERVAL)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(
                    "Unexpected error polling inner connector orderbooks. Retrying in 5s...",
                    exc_info=True,
                )
                await asyncio.sleep(5.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Diffs come through listen_for_subscriptions as snapshots."""
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Initial snapshots for each trading pair."""
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot_msg = await self._order_book_snapshot(trading_pair)
                        output.put_nowait(snapshot_msg)
                    except Exception:
                        self.logger().warning(
                            f"Failed to get snapshot for {trading_pair}",
                            exc_info=True,
                        )
                await asyncio.sleep(60.0)
            except asyncio.CancelledError:
                raise

    async def _parse_order_book_diff_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        pass

    async def _parse_trade_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        return self._diff_messages_queue_key

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        try:
            if trading_pair not in self._trading_pairs:
                self._trading_pairs.append(trading_pair)
            # Also subscribe inner connector's WS
            slug = self._connector._trading_pair_to_slug(trading_pair)
            if slug:
                inner = self._connector._inner_connector
                if inner:
                    await inner.subscribe_market(slug)
            self.logger().info(f"Subscribed to {trading_pair}")
            return True
        except Exception:
            self.logger().error(f"Failed to subscribe to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        try:
            if trading_pair in self._trading_pairs:
                self._trading_pairs.remove(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair}")
            return True
        except Exception:
            self.logger().error(f"Failed to unsubscribe from {trading_pair}")
            return False
