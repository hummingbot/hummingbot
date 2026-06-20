import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.kalqix import (
    kalqix_constants as CONSTANTS,
    kalqix_utils as utils,
    kalqix_web_utils as web_utils,
)
from hummingbot.connector.exchange.kalqix.kalqix_auth import KalqixAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.kalqix.kalqix_exchange import KalqixExchange

# Synthetic event types emitted into the user-stream queue. Mirrors the
# pattern other Hummingbot connectors use where the data source emits
# raw exchange events and the connector's `_user_stream_event_listener`
# dispatches on type.
EVENT_ORDER_UPDATE = "ORDER_UPDATE"
EVENT_TRADE = "TRADE"


class KalqixAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    REST-only user-stream source.

    The framework normally subscribes to a WebSocket user-data stream and
    relays raw frames. KalqiX has no WS today, so this source polls two
    REST endpoints on a fixed cadence and emits synthetic events:

    - `EVENT_ORDER_UPDATE` — one per open order on every poll. The
      exchange class compares against its in-flight order state to
      detect status / remaining-quantity changes. Polling cadence:
      `USER_OPEN_ORDERS_POLL_INTERVAL` (1s).
    - `EVENT_TRADE` — one per fresh fill on every poll, de-duplicated
      by a per-pair max-timestamp cursor. Carries fee + role info.
      Polling cadence: `USER_OPEN_ORDERS_POLL_INTERVAL` (same — fills
      are correlated with orderstatus changes).

    Authenticated identity is carried by the request headers (HMAC API
    key); the endpoints we hit (`/orders?open=true`, `/users/me/trades`)
    resolve the user from auth, not from a path/query param, so we don't
    need to know the wallet up front to poll them.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: KalqixAuth,
        trading_pairs: List[str],
        connector: "KalqixExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._connector = connector
        self._trading_pairs = trading_pairs
        # Per-pair max-timestamp cursor — `/users/me/trades` is a
        # per-ticker endpoint (requires `ticker` query param), so we keep
        # one high-watermark per trading pair.
        self._last_trade_ts_us: Dict[str, int] = {}
        # Bumped after every successful poll iteration. The base class's
        # `last_recv_time` reads from a WS assistant we don't have, so
        # `exchange_py_base._is_user_stream_initialized()` would otherwise
        # stay False and `connector.ready` would never flip True.
        self._last_recv_time: float = 0.0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    # ------------------------------------------------------------------
    # The single hook the framework calls
    # ------------------------------------------------------------------

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """Replaces the base class's WS connect/subscribe/listen loop
        with a REST poll loop. Pushes synthetic event dicts to `output`
        for the connector to consume."""
        while True:
            try:
                await self._poll_open_orders(output)
                await self._poll_user_trades(output)
                self._last_recv_time = time.time()
                await self._sleep(CONSTANTS.USER_OPEN_ORDERS_POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error in user-stream poll loop; retrying in 1s"
                )
                await self._sleep(1.0)

    # ------------------------------------------------------------------
    # Pollers
    # ------------------------------------------------------------------

    async def _poll_open_orders(self, output: asyncio.Queue):
        """Walk every page of `/orders?open=true` so an account with
        more than ORDERS_MAX_PAGE_SIZE open orders isn't truncated.

        Stops when the server returns a short page (less than the
        requested `page_size`), which is the cheapest end-of-data signal
        that doesn't require trusting the `total` field. A defensive cap
        (`MAX_PAGES_PER_POLL`) bounds the worst case.
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        page_size = CONSTANTS.ORDERS_MAX_PAGE_SIZE
        for page in range(CONSTANTS.MAX_PAGES_PER_POLL):
            response = await rest_assistant.execute_request(
                url=web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL, domain=self._domain),
                params={"open": "true", "page": page, "page_size": page_size},
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.ORDERS_PATH_URL,
                is_auth_required=True,
            )
            orders = response.get("data") or []
            for order in orders:
                output.put_nowait({"event_type": EVENT_ORDER_UPDATE, "order": order})
            if len(orders) < page_size:
                return
        self.logger().warning(
            f"Open-order poll hit MAX_PAGES_PER_POLL "
            f"({CONSTANTS.MAX_PAGES_PER_POLL}) without exhausting pages; "
            "some open orders may not have been processed this cycle."
        )

    async def _poll_user_trades(self, output: asyncio.Queue):
        """Per-pair trade poll.

        The endpoint returns trades sorted DESCENDING by `timestamp`,
        paginated. Naive approach (just page 0) drops trades when a
        burst between polls produces more than one page of fills, since
        advancing the cursor to the newest-seen ts skips everything
        older that we never read.

        Strategy: walk pages forward (newer → older) until we see a
        trade at-or-before our cursor, then emit oldest-first.

        Cold start (cursor == 0) is special-cased: we only read the
        first page and use it to prime the cursor, then skip emission.
        The connector tracks order fills via its own placement flow —
        replaying historical fills that pre-date the bot's startup just
        produces noise (no tracked order matches them) and would spend
        up to MAX_PAGES_PER_POLL × pages worth of rate limit on the
        first tick.

        Dedupe is by strict `timestamp > cursor`. KalqiX trade
        timestamps are microseconds from the matching engine, and the
        engine processes a ticker sequentially, so two distinct trades
        on the same pair
        cannot share a microsecond. A compound `(timestamp, trade_id)`
        cursor would be more defensive but adds complexity for no
        observed gain; revisit if the engine ever clamps timestamp
        resolution coarser than µs.
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        page_size = CONSTANTS.TRADES_MAX_PAGE_SIZE
        for trading_pair in (self._trading_pairs or []):
            ticker = utils.convert_to_exchange_ticker_path(trading_pair)
            cursor = self._last_trade_ts_us.get(trading_pair, 0)
            collected: List[Dict[str, Any]] = []
            cold_start = cursor == 0
            try:
                # Cold start primes the cursor from page 0 only.
                pages_to_walk = 1 if cold_start else CONSTANTS.MAX_PAGES_PER_POLL
                for page in range(pages_to_walk):
                    response = await rest_assistant.execute_request(
                        url=web_utils.rest_url(CONSTANTS.USER_TRADES_PATH_URL, domain=self._domain),
                        params={"ticker": ticker, "page": page, "page_size": page_size},
                        method=RESTMethod.GET,
                        throttler_limit_id=CONSTANTS.USER_TRADES_PATH_URL,
                        is_auth_required=True,
                    )
                    trades = response.get("data") or []
                    if not trades:
                        break
                    if cold_start:
                        # Prime the cursor from page 0 max; don't emit.
                        self._last_trade_ts_us[trading_pair] = max(
                            int(t.get("timestamp", 0)) for t in trades
                        )
                        break
                    # Trades are descending by timestamp. Take everything
                    # strictly newer than the cursor; if the page contains
                    # one trade at/older than the cursor, we're done.
                    saw_old = False
                    for trade in trades:
                        ts = int(trade.get("timestamp", 0))
                        if ts > cursor:
                            collected.append(trade)
                        else:
                            saw_old = True
                    if saw_old or len(trades) < page_size:
                        break
                else:
                    if not cold_start:
                        self.logger().warning(
                            f"User-trades poll for {trading_pair} hit "
                            f"MAX_PAGES_PER_POLL without reaching cursor "
                            f"{cursor}; advancing to newest seen."
                        )
            except Exception:
                self.logger().exception(
                    f"Failed user-trades poll for {trading_pair}; will retry"
                )
                continue
            if not collected:
                continue
            # Emit oldest → newest so downstream sequencing is intuitive.
            collected.sort(key=lambda t: int(t.get("timestamp", 0)))
            for trade in collected:
                output.put_nowait({"event_type": EVENT_TRADE, "trade": trade})
            self._last_trade_ts_us[trading_pair] = int(collected[-1]["timestamp"])

    # ------------------------------------------------------------------
    # Required no-op hooks — base class abstract methods we won't use
    # ------------------------------------------------------------------

    async def _connected_websocket_assistant(self) -> WSAssistant:  # pragma: no cover
        raise NotImplementedError("KalqiX connector is REST-only")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):  # pragma: no cover
        raise NotImplementedError("KalqiX connector is REST-only")
