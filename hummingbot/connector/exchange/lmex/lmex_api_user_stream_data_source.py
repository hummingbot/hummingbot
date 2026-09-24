import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.lmex import lmex_constants as CONSTANTS
from hummingbot.connector.exchange.lmex import lmex_web_utils as web_utils
from hummingbot.connector.exchange.lmex.lmex_auth import LmexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lmex.lmex_exchange import LmexExchange

# Synthetic event type keys used to route events in the exchange's _user_stream_event_listener.
EVENT_TYPE_ORDER_UPDATE = "lmex_order_update"
EVENT_TYPE_TRADE_UPDATE = "lmex_trade_update"
EVENT_TYPE_BALANCE_UPDATE = "lmex_balance_update"

# How frequently to poll private REST endpoints (seconds)
_POLL_INTERVAL = CONSTANTS.SHORT_POLL_INTERVAL


class LmexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    REST-polling user stream data source for LMEX spot.

    LMEX does not yet publish a WebSocket API for private user data.  This class
    implements polling of the private REST endpoints and synthesises the update
    events that ExchangePyBase's _user_stream_event_listener expects.

    Emitted event shapes
    --------------------
    Order update:
        {"type": EVENT_TYPE_ORDER_UPDATE, "data": <order dict from LMEX>}

    Trade update:
        {"type": EVENT_TYPE_TRADE_UPDATE, "data": <trade dict from LMEX>}

    Balance update:
        {"type": EVENT_TYPE_BALANCE_UPDATE, "data": [<wallet entry>, ...]}
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: LmexAuth,
        trading_pairs: List[str],
        connector: "LmexExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

        # Track which trade IDs we have already emitted to avoid duplicates.
        self._seen_trade_ids: set = set()
        # Track the last known order state to emit updates only on change.
        self._last_order_states: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # UserStreamTrackerDataSource interface
    # ------------------------------------------------------------------

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        WebSocket private stream is not yet implemented for LMEX.
        TODO: implement once LMEX publishes WS API docs for private channels.
        """
        raise NotImplementedError(
            "TODO: LMEX WebSocket private stream not yet implemented — using REST polling fallback."
        )

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        raise NotImplementedError(
            "TODO: LMEX WebSocket private stream not yet implemented — using REST polling fallback."
        )

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Overrides the base class to implement REST-polling instead of WebSocket listening.
        Polls open orders, trade history, and wallet balance at _POLL_INTERVAL and pushes
        synthetic events into the output queue.
        """
        while True:
            try:
                await self._poll_and_emit(output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error while polling LMEX user stream. Retrying after delay."
                )
            await self._sleep(_POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Internal polling helpers
    # ------------------------------------------------------------------

    async def _poll_and_emit(self, output: asyncio.Queue):
        await self._emit_open_order_updates(output)
        await self._emit_trade_updates(output)
        await self._emit_balance_update(output)

    async def _emit_open_order_updates(self, output: asyncio.Queue):
        """
        Polls GET /api/v3.2/user/open_orders for each tracked trading pair and
        emits an order-update event for any order whose status has changed.
        """
        for trading_pair in self._trading_pairs:
            try:
                symbol = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair
                )
                rest_assistant = await self._api_factory.get_rest_assistant()
                open_orders: List[Dict[str, Any]] = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(
                        endpoint=CONSTANTS.OPEN_ORDERS_PATH_URL, domain=self._domain
                    ),
                    params={"symbol": symbol},
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.OPEN_ORDERS_PATH_URL,
                    is_auth_required=True,
                )
                if not isinstance(open_orders, list):
                    continue
                for order in open_orders:
                    order_id = order.get("orderID", "")
                    # Open-orders endpoint returns string orderState ("STATUS_ACTIVE" /
                    # "STATUS_INACTIVE") rather than numeric status codes.  Use it as
                    # the change-detection key; the exchange listener will re-query for
                    # the full numeric status via _request_order_status if needed.
                    state_key = order.get("orderState") or order.get("status")
                    if self._last_order_states.get(order_id) != state_key:
                        self._last_order_states[order_id] = state_key
                        output.put_nowait({"type": EVENT_TYPE_ORDER_UPDATE, "data": order})
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(
                    f"Error polling open orders for {trading_pair}.", exc_info=True
                )

    async def _emit_trade_updates(self, output: asyncio.Queue):
        """
        Polls GET /api/v3.2/user/trade_history for each tracked trading pair and
        emits trade-update events for any fills not yet seen.
        """
        for trading_pair in self._trading_pairs:
            try:
                symbol = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair
                )
                rest_assistant = await self._api_factory.get_rest_assistant()
                trades: List[Dict[str, Any]] = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(
                        endpoint=CONSTANTS.TRADE_HISTORY_PATH_URL, domain=self._domain
                    ),
                    params={"symbol": symbol},
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.TRADE_HISTORY_PATH_URL,
                    is_auth_required=True,
                )
                if not isinstance(trades, list):
                    continue
                for trade in trades:
                    trade_id = str(trade.get("tradeId", ""))
                    if trade_id and trade_id not in self._seen_trade_ids:
                        self._seen_trade_ids.add(trade_id)
                        output.put_nowait({"type": EVENT_TYPE_TRADE_UPDATE, "data": trade})
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(
                    f"Error polling trade history for {trading_pair}.", exc_info=True
                )

    async def _emit_balance_update(self, output: asyncio.Queue):
        """
        Polls GET /api/v3.2/user/wallet and emits a balance-update event.
        """
        try:
            rest_assistant = await self._api_factory.get_rest_assistant()
            wallet: List[Dict[str, Any]] = await rest_assistant.execute_request(
                url=web_utils.private_rest_url(
                    endpoint=CONSTANTS.USER_WALLET_PATH_URL, domain=self._domain
                ),
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.USER_WALLET_PATH_URL,
                is_auth_required=True,
            )
            if isinstance(wallet, list):
                output.put_nowait({"type": EVENT_TYPE_BALANCE_UPDATE, "data": wallet})
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning("Error polling wallet balance.", exc_info=True)

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    @property
    def last_recv_time(self) -> float:
        return time.time()
