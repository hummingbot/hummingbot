import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitget import bitget_constants as CONSTANTS
from hummingbot.connector.exchange.bitget.bitget_auth import BitgetAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSPlainTextRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange


class BitgetAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BitgetAuth,
        trading_pairs: List[str],
        connector: 'BitgetExchange',
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._pong_response_event = None
        self._pong_received_event = asyncio.Event()
        self._exchange_ping_task: Optional[asyncio.Task] = None

    async def _authenticate(self, websocket_assistant: WSAssistant):
        """
        Authenticates user to websocket
        """
        await websocket_assistant.send(
            WSJSONRequest({
                "op": "login",
                "args": [self._auth.get_ws_auth_payload()]
            })
        )
        response: WSResponse = await websocket_assistant.receive()
        message = response.data

        if (message["event"] != "login" and message["code"] != "0"):
            self.logger().error(
                f"Error authenticating the private websocket connection. Response message {message}"
            )
            raise IOError("Private websocket connection authentication failed")

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0 and "event" not in event_message and "data" in event_message:
            queue.put_nowait(event_message)
        elif event_message == CONSTANTS.PUBLIC_WS_PONG:
            self._pong_received_event.set()
        elif "event" in event_message:
            if event_message["event"] == "error":
                self.logger().error(f"Private channel subscription failed ({event_message})")
                raise IOError(f"Private channel subscription failed ({event_message})")
        else:
            self.logger().error(f"Invalid event message ({event_message})")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):

        try:
            subscription_topics = []

            for channel in [CONSTANTS.WS_ACCOUNT_ENDPOINT, CONSTANTS.WS_FILL_ENDPOINT]:
                subscription_topics.append({
                    "instType": "SPOT",
                    "channel": channel,
                    "coin": "default"
                })

            for trading_pair in self._trading_pairs:
                subscription_topics.append({
                    "instType": "SPOT",
                    "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                    "instId": await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                })
            await websocket_assistant.send(
                WSJSONRequest({
                    "op": "subscribe",
                    "args": subscription_topics
                })
            )
            self.logger().info("Subscribed to private channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to private channels...")
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(
            ws_url=CONSTANTS.WSS_PRIVATE_URL,
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        await self._authenticate(websocket_assistant)

        return websocket_assistant

    async def _send_ping(self, websocket_assistant: WSAssistant) -> None:
        ping_request = WSPlainTextRequest(CONSTANTS.PUBLIC_WS_PING)

        await websocket_assistant.send(ping_request)
        self.logger().info("Ping sent for user stream")

    def _max_heartbeat_response_delay(self):
        return 30
