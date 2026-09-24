import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth import LmexPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_derivative import LmexPerpetualDerivative

# Internal event-type keys used to tag synthetic messages
_ORDERS_EVENT = "lmex_perp.open_orders"
_TRADES_EVENT = "lmex_perp.trade_history"
_POSITIONS_EVENT = "lmex_perp.positions"
_WALLET_EVENT = "lmex_perp.wallet"


class LmexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    REST-polling user stream for LMEX Perpetual.

    LMEX Futures does not offer a private WebSocket feed, so this class
    periodically polls the authenticated REST endpoints and synthesises
    messages that the connector's ``_user_stream_event_listener`` can consume.

    Synthetic message format (dict):
        {
            "channel": <_ORDERS_EVENT | _TRADES_EVENT | _POSITIONS_EVENT | _WALLET_EVENT>,
            "data":    <raw list or dict returned by the REST endpoint>,
        }
    """

    POLL_INTERVAL: float = 5.0          # seconds between polls
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: LmexPerpetualAuth,
        trading_pairs: List[str],
        connector: "LmexPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    @property
    def last_recv_time(self) -> float:
        return self._time()

    # ------------------------------------------------------------------
    # Override listen_for_user_stream entirely (no WebSocket needed)
    # ------------------------------------------------------------------

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Polls authenticated REST endpoints on a fixed interval and puts
        synthesised event messages into *output*.
        """
        while True:
            try:
                await self._poll_and_emit(output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error while polling LMEX Perpetual user stream. "
                    "Retrying in 5 seconds..."
                )
            await self._sleep(self.POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Stubs required by the base class (not used in REST-polling mode)
    # ------------------------------------------------------------------

    async def _connected_websocket_assistant(self) -> WSAssistant:
        raise NotImplementedError("LMEX Perpetual uses REST polling; no WebSocket user stream.")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        raise NotImplementedError("LMEX Perpetual uses REST polling; no WebSocket user stream.")

    # ------------------------------------------------------------------
    # Polling logic
    # ------------------------------------------------------------------

    async def _poll_and_emit(self, output: asyncio.Queue):
        rest_assistant = await self._api_factory.get_rest_assistant()

        # 1. Wallet / balance update
        try:
            wallet_data = await rest_assistant.execute_request(
                url=web_utils.private_rest_url(
                    endpoint=CONSTANTS.USER_WALLET_PATH_URL, domain=self._domain
                ),
                params={"wallet": "CROSS@"},
                method=RESTMethod.GET,
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.USER_WALLET_PATH_URL,
            )
            output.put_nowait({"channel": _WALLET_EVENT, "data": wallet_data})
        except Exception:
            self.logger().debug("LMEX Perpetual: error polling wallet", exc_info=True)

        # 2. Open orders + trade history per trading pair
        for trading_pair in self._trading_pairs:
            try:
                ex_symbol = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair
                )
            except Exception:
                continue

            # Open orders
            try:
                open_orders = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(
                        endpoint=CONSTANTS.OPEN_ORDERS_PATH_URL, domain=self._domain
                    ),
                    params={"symbol": ex_symbol},
                    method=RESTMethod.GET,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.OPEN_ORDERS_PATH_URL,
                )
                if open_orders:
                    output.put_nowait({"channel": _ORDERS_EVENT, "data": open_orders})
            except Exception:
                self.logger().debug(
                    f"LMEX Perpetual: error polling open orders for {trading_pair}", exc_info=True
                )

            # Trade history
            try:
                trade_history = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(
                        endpoint=CONSTANTS.TRADE_HISTORY_PATH_URL, domain=self._domain
                    ),
                    params={"symbol": ex_symbol},
                    method=RESTMethod.GET,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.TRADE_HISTORY_PATH_URL,
                )
                if trade_history:
                    output.put_nowait({"channel": _TRADES_EVENT, "data": trade_history})
            except Exception:
                self.logger().debug(
                    f"LMEX Perpetual: error polling trade history for {trading_pair}", exc_info=True
                )

            # Positions
            try:
                positions = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(
                        endpoint=CONSTANTS.POSITIONS_PATH_URL, domain=self._domain
                    ),
                    params={"symbol": ex_symbol},
                    method=RESTMethod.GET,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.POSITIONS_PATH_URL,
                )
                if positions:
                    output.put_nowait({"channel": _POSITIONS_EVENT, "data": positions})
            except Exception:
                self.logger().debug(
                    f"LMEX Perpetual: error polling positions for {trading_pair}", exc_info=True
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    def _time(self) -> float:
        return time.time()


# Export channel keys so the derivative can import them
ORDERS_EVENT_KEY = _ORDERS_EVENT
TRADES_EVENT_KEY = _TRADES_EVENT
POSITIONS_EVENT_KEY = _POSITIONS_EVENT
WALLET_EVENT_KEY = _WALLET_EVENT
