import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, NoReturn, Optional

from hummingbot.connector.exchange.bitget import bitget_constants as CONSTANTS, bitget_web_utils as web_utils
from hummingbot.connector.exchange.bitget.bitget_auth import BitgetAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSPlainTextRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange


class BitgetAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Data source for retrieving user stream data from the Bitget exchange via WebSocket APIs.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BitgetAuth,
        trading_pairs: List[str],
        connector: 'BitgetExchange',
        api_factory: WebAssistantsFactory,
    ) -> None:
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._ping_task: Optional[asyncio.Task] = None

    async def _authenticate(self, websocket_assistant: WSAssistant) -> None:
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

    async def _parse_pong_message(self) -> None:
        self.logger().debug("PING-PONG message for user stream completed")

    async def _process_message_for_unknown_channel(
        self,
        event_message: Dict[str, Any]
    ) -> None:
        if event_message == CONSTANTS.PUBLIC_WS_PONG_RESPONSE:
            await self._parse_pong_message()
        elif "event" in event_message:
            if event_message["event"] == "error":
                message = event_message.get("msg", "Unknown error")
                error_code = event_message.get("code", "Unknown code")
                self.logger().error(
                    f"Failed to subscribe to private channels: {message} ({error_code})"
                )

            if event_message["event"] == "subscribe":
                channel: str = event_message["arg"]["channel"]
                self.logger().info(f"Subscribed to private channel: {channel.upper()}")
        else:
            self.logger().warning(f"Message for unknown channel received: {event_message}")

    async def _process_event_message(
        self,
        event_message: Dict[str, Any],
        queue: asyncio.Queue
    ) -> None:
        if "arg" in event_message and "action" in event_message:
            queue.put_nowait(event_message)
        else:
            await self._process_message_for_unknown_channel(event_message)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
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
            ws_url=web_utils.private_ws_url(),
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        await self._authenticate(websocket_assistant)

        return websocket_assistant

    async def _send_ping(self, websocket_assistant: WSAssistant) -> None:
        await websocket_assistant.send(
            WSPlainTextRequest(CONSTANTS.PUBLIC_WS_PING_REQUEST)
        )

    async def send_interval_ping(self, websocket_assistant: WSAssistant) -> None:
        """
        Coroutine to send PING messages periodically.

        :param websocket_assistant: The websocket assistant to use to send the PING message.
        """
        try:
            while True:
                await self._send_ping(websocket_assistant)
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        except asyncio.CancelledError:
            self.logger().info("Interval PING task cancelled")
            raise
        except Exception:
            self.logger().exception("Error sending interval PING")

    async def listen_for_user_stream(self, output: asyncio.Queue) -> NoReturn:
        while True:
            try:
                self._ws_assistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(websocket_assistant=self._ws_assistant)
                self._ping_task = asyncio.create_task(self.send_interval_ping(self._ws_assistant))
                await self._process_websocket_messages(
                    websocket_assistant=self._ws_assistant,
                    queue=output
                )
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(
                    f"The websocket connection was closed ({connection_exception})"
                )
            except Exception:
                self.logger().exception(
                    "Unexpected error while listening to user stream. Retrying after 5 seconds..."
                )
                await self._sleep(1.0)
            finally:
                if self._ping_task is not None:
                    self._ping_task.cancel()
                    try:
                        await self._ping_task
                    except asyncio.CancelledError:
                        pass
                    self._ping_task = None
                await self._on_user_stream_interruption(websocket_assistant=self._ws_assistant)
                self._ws_assistant = None
