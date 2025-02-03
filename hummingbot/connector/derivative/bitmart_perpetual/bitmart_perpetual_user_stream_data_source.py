import asyncio
from typing import TYPE_CHECKING, List, Optional

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_auth import BitmartPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative import (
        BitmartPerpetualDerivative,
    )


class BitmartPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: BitmartPerpetualAuth,
            connector: 'BitmartPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):

        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
        self._listen_for_user_stream_task = None

    @property
    def last_recv_time(self) -> float:
        t = 0.0
        if len(self._ws_assistants) > 0:
            t = min([wsa.last_recv_time for wsa in self._ws_assistants])
        return t

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        ws: Optional[WSAssistant] = None
        url = web_utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)
        while True:
            try:
                ws = await self._get_connected_websocket_assistant(url)
                self._ws_assistants.append(ws)
                await self._subscribe_to_channels(ws, url)
                await ws.ping()  # to update last_recv_timestamp
                await self._process_websocket_messages(websocket_assistant=ws, queue=output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    f"Unexpected error while listening to user stream {url}. Retrying after 5 seconds..."
                )
                await self._sleep(5.0)
            finally:
                await self._on_user_stream_interruption(ws)
                ws and self._ws_assistants.remove(ws)

    async def _get_connected_websocket_assistant(self, ws_url: str) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE)
        await self._authenticate(ws)
        return ws

    async def _authenticate(self, ws: WSAssistant):
        """
        Authenticates user to websocket
        """
        login_request: WSJSONRequest = WSJSONRequest(payload=self._auth.get_ws_login_with_args())
        await ws.send(login_request)
        response: WSResponse = await ws.receive()
        message = response.data

        if not message["success"]:
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError("Private websocket connection authentication failed")

    async def _subscribe_to_channels(self, ws: WSAssistant, url: str):
        try:
            channels_to_subscribe: List[str] = [
                CONSTANTS.WS_POSITIONS_CHANNEL,
                CONSTANTS.WS_ORDERS_CHANNEL,
                CONSTANTS.WS_ACCOUNT_CHANNEL
            ]

            tasks = []
            for channel in channels_to_subscribe:
                payload = {
                    "action": "subscribe",
                    "args": [channel]
                }
                task = ws.send(WSJSONRequest(payload))
                tasks.append(task)

            await asyncio.gather(*tasks)

            self.logger().info(
                f"Subscribed to private account and orders channels {url}..."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Unexpected error occurred subscribing to private account and orders channels {url}..."
            )
            raise

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass  # unused

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused
