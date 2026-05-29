import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.kalqix import (
    kalqix_constants as CONSTANTS,
    kalqix_utils as utils,
    kalqix_web_utils as web_utils,
)
from hummingbot.connector.exchange.kalqix.kalqix_order_book import KalqixOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.kalqix.kalqix_exchange import KalqixExchange


class KalqixAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    KalqiX exposes no WebSocket today, so this data source replaces the
    WS-driven loops in `OrderBookTrackerDataSource` with REST pollers:

    - **Orderbook snapshots** — polled every
      `ORDER_BOOK_SNAPSHOT_POLL_INTERVAL` (500ms) per pair. Each poll
      emits a single SNAPSHOT message; Hummingbot's tracker overwrites
      the local book on each. No diffs.
    - **Public trades** — polled every `TRADE_TAPE_POLL_INTERVAL` (1s)
      per pair. A per-pair `last_trade_ts_us` cursor de-dupes; only
      trades with `timestamp > cursor` are emitted.

    `listen_for_subscriptions` and `listen_for_order_book_diffs` are
    no-ops (we have nothing to subscribe to and no diff stream). The
    snapshot/trade loops run as their own tasks, scheduled by
    `OrderBookTracker.start()` via `ev_loop.create_task`, so this works
    with the framework's normal task management.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "KalqixExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        # Per-pair monotonic cursor (ms) for trade-tape de-duplication.
        self._last_trade_ts_us: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Required hooks
    # ------------------------------------------------------------------

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        # Delegate to the connector so we share one cached fetch path.
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """Hit `/markets/{ticker}/order-book` and return the raw response."""
        ticker_url = utils.convert_to_exchange_ticker_path(trading_pair)
        path = CONSTANTS.SNAPSHOT_PATH_URL.format(ticker=ticker_url)
        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.rest_url(path, domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """Build a SNAPSHOT `OrderBookMessage` from one REST poll."""
        snapshot = await self._request_order_book_snapshot(trading_pair)
        return KalqixOrderBook.snapshot_message_from_exchange(
            snapshot,
            timestamp=time.time(),
            metadata={"trading_pair": trading_pair},
        )

    # ------------------------------------------------------------------
    # Overridden listen loops — REST poll instead of WS subscribe
    # ------------------------------------------------------------------

    async def listen_for_subscriptions(self):
        """No WebSocket. The snapshot + trade loops below do all the
        work; this loop just needs to stay alive so the tracker doesn't
        treat it as crashed and restart it in a hot loop."""
        while True:
            await self._sleep(3600.0)

    async def listen_for_order_book_snapshots(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """Poll each pair's orderbook on a fixed cadence and emit a
        SNAPSHOT message per poll. With no WS diff stream, each snapshot
        is the source of truth — the tracker overwrites the local book."""
        while True:
            try:
                for trading_pair in (self._trading_pairs or []):
                    try:
                        snapshot_msg = await self._order_book_snapshot(trading_pair)
                        output.put_nowait(snapshot_msg)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().exception(
                            f"Failed orderbook snapshot for {trading_pair}; will retry"
                        )
                await self._sleep(CONSTANTS.ORDER_BOOK_SNAPSHOT_POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in snapshot poll loop")
                await self._sleep(1.0)

    async def listen_for_order_book_diffs(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """No diff stream. Stay alive idle."""
        while True:
            await self._sleep(3600.0)

    async def listen_for_trades(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """Poll the public trade tape per pair; emit one TRADE message
        per fresh trade. Cursor is the highest `timestamp` seen so the
        loop is idempotent across iterations."""
        while True:
            try:
                for trading_pair in (self._trading_pairs or []):
                    try:
                        await self._emit_new_trades(trading_pair, output)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().exception(
                            f"Failed trade-tape poll for {trading_pair}; will retry"
                        )
                await self._sleep(CONSTANTS.TRADE_TAPE_POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in trade poll loop")
                await self._sleep(1.0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _emit_new_trades(self, trading_pair: str, output: asyncio.Queue):
        """Walk trade pages newer→older for a pair, emitting everything
        past the cursor in oldest-first order, then advance the cursor.

        Naive page-0 polling drops trades when a burst between polls
        produces more than one page of fills (since advancing the cursor
        to the newest-seen ts skips everything older we never read).

        Cold start (cursor == 0) is special-cased: read page 0 once to
        prime the cursor and skip emission. Strategies are generally
        only interested in the live tape; backfilling historical trades
        on every connector restart would spam the orderbook tracker.

        Dedupe is by strict `timestamp > cursor`. KalqiX trade
        timestamps are microseconds (matching engine processes a ticker
        sequentially), so two distinct trades on the same pair cannot
        share a µs and a same-cursor collision can't happen in
        practice. A `(timestamp, trade_id)` cursor would be more
        defensive but isn't worth the complexity unless engine
        resolution ever coarsens.
        """
        ticker_url = utils.convert_to_exchange_ticker_path(trading_pair)
        path = CONSTANTS.TRADES_PATH_URL.format(ticker=ticker_url)
        rest_assistant = await self._api_factory.get_rest_assistant()
        page_size = CONSTANTS.TRADES_MAX_PAGE_SIZE
        cursor = self._last_trade_ts_us.get(trading_pair, 0)
        cold_start = cursor == 0

        collected: List[Dict[str, Any]] = []
        pages_to_walk = 1 if cold_start else CONSTANTS.MAX_PAGES_PER_POLL
        for page in range(pages_to_walk):
            response = await rest_assistant.execute_request(
                url=web_utils.rest_url(path, domain=self._domain),
                params={"page": page, "page_size": page_size},
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.TRADES_PATH_URL,
            )
            trades = response.get("data") or []
            if not trades:
                break
            if cold_start:
                self._last_trade_ts_us[trading_pair] = max(
                    int(t["timestamp"]) for t in trades
                )
                return
            saw_old = False
            for trade in trades:
                ts = int(trade["timestamp"])
                if ts > cursor:
                    collected.append(trade)
                else:
                    saw_old = True
            if saw_old or len(trades) < page_size:
                break
        else:
            if not cold_start:
                self.logger().warning(
                    f"Trade-tape poll for {trading_pair} hit MAX_PAGES_PER_POLL "
                    f"without reaching cursor {cursor}; advancing to newest seen."
                )

        if not collected:
            return

        # Emit oldest → newest so strategies see a strictly monotonic tape.
        collected.sort(key=lambda t: int(t["timestamp"]))
        for trade in collected:
            trade_msg = KalqixOrderBook.trade_message_from_exchange(
                trade,
                metadata={"trading_pair": trading_pair},
            )
            output.put_nowait(trade_msg)

        self._last_trade_ts_us[trading_pair] = int(collected[-1]["timestamp"])

    # ------------------------------------------------------------------
    # WS-only hooks left as no-ops (tracker never invokes them after
    # `listen_for_subscriptions` is overridden, but keep them defined
    # so the abstract-method check doesn't bite).
    # ------------------------------------------------------------------

    async def _connected_websocket_assistant(self) -> WSAssistant:  # pragma: no cover
        raise NotImplementedError("KalqiX connector is REST-only")

    async def _subscribe_channels(self, ws: WSAssistant):  # pragma: no cover
        raise NotImplementedError("KalqiX connector is REST-only")

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        return True

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:  # pragma: no cover
        return ""

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):  # pragma: no cover
        raise NotImplementedError("Trades flow via the REST poll loop")

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):  # pragma: no cover
        raise NotImplementedError("KalqiX has no diff stream")
