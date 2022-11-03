import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.whitebit import whitebit_constants as CONSTANTS, whitebit_web_utils as web_utils
from hummingbot.connector.exchange.whitebit.whitebit_auth import WhitebitAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from .whitebit_exchange import WhitebitExchange


class WhitebitAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: WhitebitAuth,
        trading_pairs: List[str],
        connector: "WhitebitExchange",
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        rest_assistant = await self._api_factory.get_rest_assistant()
        token_response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH),
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH,
            is_auth_required=True,
        )

        if "websocket_token" not in token_response:
            raise IOError(f"Could not get an authentication token for private websocket ({token_response})")

        token = token_response["websocket_token"]

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WHITEBIT_WS_URI)

        auth_payload = {"id": 0, "method": "authorize", "params": [token, "public"]}

        login_request: WSJSONRequest = WSJSONRequest(payload=auth_payload)

        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
            await ws.send(login_request)

        response: WSResponse = await ws.receive()
        message = response.data
        if message.get("result", {}).get("status") != "success":
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError(f"Private websocket connection authentication failed ({message})")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param ws: the websocket assistant used to connect to the exchange
        """
        tokens = set()
        symbols = list()

        for trading_pair in self._trading_pairs:
            tokens.update(trading_pair.split("-"))
            symbols.append(await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair))

        try:
            balance_payload = {"id": 1, "method": "balanceSpot_subscribe", "params": sorted(list(tokens))}
            subscribe_balance_request: WSJSONRequest = WSJSONRequest(payload=balance_payload)

            trades_payload = {"id": 2, "method": "deals_subscribe", "params": [symbols]}
            subscribe_trades_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

            orders_payload = {"id": 3, "method": "ordersPending_subscribe", "params": symbols}
            subscribe_orders_request: WSJSONRequest = WSJSONRequest(payload=orders_payload)

            await websocket_assistant.send(subscribe_balance_request)
            await websocket_assistant.send(subscribe_trades_request)
            await websocket_assistant.send(subscribe_orders_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to private order changes and balance updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0 and event_message.get("method") in [
            CONSTANTS.WHITEBIT_WS_PRIVATE_BALANCE_CHANNEL,
            CONSTANTS.WHITEBIT_WS_PRIVATE_TRADES_CHANNEL,
            CONSTANTS.WHITEBIT_WS_PRIVATE_ORDERS_CHANNEL,
        ]:
            queue.put_nowait(event_message)
