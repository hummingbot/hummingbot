import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSPlainTextRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative


class BitgetPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BitgetPerpetualAuth,
        trading_pairs: List[str],
        connector: 'BitgetPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = None,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._pong_response_event = None

    async def _authenticate(self, ws: WSAssistant):
        """
        Authenticates user to websocket
        """
        auth_payload: List[str] = self._auth.get_ws_auth_payload()
        payload = {"op": "login", "args": auth_payload}
        login_request: WSJSONRequest = WSJSONRequest(payload=payload)
        await ws.send(login_request)
        response: WSResponse = await ws.receive()
        message = response.data

        if (
            message["event"] != "login"
            and message["code"] != "0"
        ):
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError("Private websocket connection authentication failed")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant=websocket_assistant, queue=queue),
                    timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE)
            except asyncio.TimeoutError:
                if self._pong_response_event and not self._pong_response_event.is_set():
                    # The PONG response for the previous PING request was never received
                    raise IOError("The user stream channel is unresponsive (pong response not received)")
                self._pong_response_event = asyncio.Event()
                await self._send_ping(websocket_assistant=websocket_assistant)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message == CONSTANTS.WS_PONG_RESPONSE and self._pong_response_event:
            self._pong_response_event.set()
        elif "event" in event_message:
            if event_message["event"] == "error":
                raise IOError(f"Private channel subscription failed ({event_message})")
        else:
            await super()._process_event_message(event_message=event_message, queue=queue)

    async def _send_ping(self, websocket_assistant: WSAssistant):
        ping_request = WSPlainTextRequest(payload=CONSTANTS.WS_PING_REQUEST)
        await websocket_assistant.send(ping_request)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            product_types = set([await self._connector.product_type_for_trading_pair(trading_pair=trading_pair)
                                 for trading_pair in self._trading_pairs])
            subscription_payloads = []

            for product_type in product_types:
                subscription_payloads.append(
                    {
                        "instType": product_type.upper(),
                        "channel": CONSTANTS.WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME,
                        "instId": "default"
                    }
                )
                subscription_payloads.append(
                    {
                        "instType": product_type.upper(),
                        "channel": CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME,
                        "instId": "default"
                    }
                )
                subscription_payloads.append(
                    {
                        "instType": product_type.upper(),
                        "channel": CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME,
                        "instId": "default"
                    }
                )

            payload = {
                "op": "subscribe",
                "args": subscription_payloads
            }
            subscription_request = WSJSONRequest(payload)

            await websocket_assistant.send(subscription_request)

            self.logger().info("Subscribed to private account, position and orders channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                "Unexpected error occurred subscribing to account, position and orders channels..."
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_URL,
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE)
        await self._authenticate(ws)
        return ws
