import asyncio
import logging
import time
from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import (
    OrderBookTrackerDataSource,
)

from kuru_sdk_py.feed.orderbook_ws import (
    FrontendOrderbookUpdate,
)

from hummingbot.connector.exchange.kuru.kuru_order_book import KuruOrderBook

logger = logging.getLogger(__name__)


class KuruAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Orderbook data source for Kuru DEX.

    Consumes FrontendOrderbookUpdate messages from an asyncio.Queue
    that is fed by the KuruExchange connector via the SDK's orderbook
    WebSocket callback. Converts them to OrderBookMessage snapshots.

    Kuru sends full orderbook state with each update (not diffs),
    so listen_for_order_book_diffs is a no-op and all data flows
    through listen_for_order_book_snapshots.
    """

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "KuruExchange",  # noqa: F821
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._last_update_id: int = 0

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return last traded prices from the connector's cache."""
        return {
            pair: self._connector.last_traded_prices.get(pair, 0.0)
            for pair in trading_pairs
        }

    async def listen_for_subscriptions(self):
        """
        No-op. The SDK manages the orderbook WebSocket connection.
        Data flows via the shared queue populated by KuruExchange's
        orderbook callback.
        """
        await asyncio.sleep(float("inf"))

    async def listen_for_order_book_diffs(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """No-op. Kuru sends full snapshots, not incremental diffs."""
        await asyncio.sleep(float("inf"))

    async def listen_for_order_book_snapshots(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """
        Consume orderbook updates from the SDK queue and emit
        OrderBookMessage snapshots.
        """
        logger.info("listen_for_order_book_snapshots: started, waiting for updates...")
        while True:
            try:
                update: FrontendOrderbookUpdate = (
                    await self._connector.sdk_orderbook_queue.get()
                )

                # Only process updates that include full orderbook state
                if update.b is None and update.a is None:
                    logger.debug("listen_for_order_book_snapshots: skipping update with no bids/asks")
                    continue

                trading_pair = self._connector.trading_pairs[0]

                # Prices and sizes arrive from the SDK queue in normalized values.
                bids = []
                if update.b:
                    for price, size in update.b:
                        if size > 0:
                            bids.append([price, size])

                asks = []
                if update.a:
                    for price, size in update.a:
                        if size > 0:
                            asks.append([price, size])

                self._last_update_id += 1
                timestamp = time.time()

                best_bid = bids[0] if bids else None
                best_ask = asks[0] if asks else None
                logger.info(
                    f"Orderbook snapshot #{self._last_update_id}: {trading_pair} — "
                    f"{len(bids)} bids, {len(asks)} asks, "
                    f"best_bid={best_bid}, best_ask={best_ask}"
                )

                snapshot_msg = KuruOrderBook.snapshot_message_from_exchange(
                    msg={
                        "trading_pair": trading_pair,
                        "update_id": self._last_update_id,
                        "bids": bids,
                        "asks": asks,
                    },
                    timestamp=timestamp,
                )
                output.put_nowait(snapshot_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error processing orderbook snapshot")
                await asyncio.sleep(1.0)

    async def listen_for_trades(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """
        Trade messages are extracted from orderbook updates in the
        exchange connector. This is a no-op here.
        """
        await asyncio.sleep(float("inf"))

    async def _order_book_snapshot(
        self, trading_pair: str
    ) -> OrderBookMessage:
        """
        Return a snapshot from the latest orderbook state.

        Falls back to an empty snapshot if no data is available yet.
        """
        logger.debug(f"_order_book_snapshot: requesting snapshot for {trading_pair}")
        # Try to get an update from the queue with a short timeout
        try:
            update = await asyncio.wait_for(
                self._connector.sdk_orderbook_queue.get(),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"_order_book_snapshot: timeout waiting for {trading_pair}, returning empty snapshot")
            # Return empty snapshot
            return KuruOrderBook.snapshot_message_from_exchange(
                msg={
                    "trading_pair": trading_pair,
                    "update_id": 0,
                    "bids": [],
                    "asks": [],
                },
                timestamp=time.time(),
            )

        # Prices and sizes arrive from the SDK queue in normalized values.
        bids = []
        if update.b:
            for price, size in update.b:
                if size > 0:
                    bids.append([price, size])

        asks = []
        if update.a:
            for price, size in update.a:
                if size > 0:
                    asks.append([price, size])

        self._last_update_id += 1
        return KuruOrderBook.snapshot_message_from_exchange(
            msg={
                "trading_pair": trading_pair,
                "update_id": self._last_update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=time.time(),
        )

    # Required abstract methods - not applicable for SDK-based connector
    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        return True
