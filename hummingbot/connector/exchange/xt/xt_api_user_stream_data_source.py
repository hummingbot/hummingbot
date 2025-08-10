import asyncio
from typing import TYPE_CHECKING, Any, List, Optional

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_auth import XtAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xt.xt_exchange import XtExchange


class XtAPIUserStreamDataSource(UserStreamTrackerDataSource):

    USER_STREAM_ID = 1

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: XtAuth,
                 trading_pairs: List[str],
                 connector: 'XtExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: XtAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue
        :param output: the queue to use to store the received messages
        """
        while True:
            try:
                self._ws_assistant = await self._connected_websocket_assistant()
                # Get the listenKey to subscribe to channels
                self._current_listen_key = await self._get_listen_key()
                self.logger().info(f"Fetched XT listenKey: {self._current_listen_key}")
                await self._subscribe_channels(websocket_assistant=self._ws_assistant)
                self.logger().info("Subscribed to private account and orders channels...")
                # Start background ping loop
                self._ping_task = asyncio.create_task(self._send_raw_ping(self._ws_assistant))
                await self._process_websocket_messages(websocket_assistant=self._ws_assistant, queue=output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
                await self._sleep(1.0)
            finally:
                await self._on_user_stream_interruption(websocket_assistant=self._ws_assistant)
                self._ws_assistant = None
                if hasattr(self, '_ping_task') and self._ping_task is not None:
                    self._ping_task.cancel()
                    try:
                        await self._ping_task
                    except Exception:
                        pass

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{CONSTANTS.WSS_URL_PRIVATE.format(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        self.logger().info("Connected to XT Private WebSocket")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {
                "method": "subscribe",
                "params": ["balance", "order"],     # trade channel doesn't have fee info
                "listenKey": self._current_listen_key,
                "id": self.USER_STREAM_ID
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await websocket_assistant.send(subscribe_request)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to private account and order streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            await self._process_event_message(event_message=data, queue=queue)

    async def _process_event_message(self, event_message: Any, queue: asyncio.Queue):
        if isinstance(event_message, dict) and len(event_message) > 0 and ("data" in event_message and "topic" in event_message):
            queue.put_nowait(event_message)

    async def _get_listen_key(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.GET_ACCOUNT_LISTENKEY, domain=self._domain),
                method=RESTMethod.POST,
                throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT,
                headers=self._auth.add_auth_to_headers(RESTMethod.POST, f"/{CONSTANTS.PUBLIC_API_VERSION}{CONSTANTS.GET_ACCOUNT_LISTENKEY}")
            )
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(f"Error fetching user stream listen key. Error: {exception}")

        return data["result"]["accessToken"]

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        self._current_listen_key = None

    async def _send_raw_ping(self, ws: WSAssistant):
        """Send a raw 'ping' string every WS_HEARTBEAT_TIME_INTERVAL seconds."""
        while True:
            try:
                await ws._connection._send_plain_text("ping")
                self.logger().info("Sent raw 'ping' string to XT WebSocket.")
            except Exception as e:
                self.logger().error(f"Error sending raw ping: {e}")
                break
            await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
