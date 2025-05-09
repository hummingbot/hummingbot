import asyncio
from typing import List, Optional

from hummingbot.connector.derivative.okx_perpetual import (
    okx_perpetual_constants as CONSTANTS,
    okx_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth import OkxPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class OkxPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: OkxPerpetualAuth,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
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
        tasks_future = None
        try:
            tasks = []
            tasks.append(
                self._listen_for_user_stream_on_url(
                    url=web_utils.wss_linear_private_url(self._domain), output=output
                )
            )
            tasks_future = asyncio.gather(*tasks)
            await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise

    async def _listen_for_user_stream_on_url(self, url: str, output: asyncio.Queue):
        ws: Optional[WSAssistant] = None
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
        auth_args: List[str] = self._auth.get_ws_auth_args()
        payload = {"op": "login", "args": auth_args}
        login_request: WSJSONRequest = WSJSONRequest(payload=payload)
        await ws.send(login_request)
        response: WSResponse = await ws.receive()
        message = response.data

        if message["event"] != "login":
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError("Private websocket connection authentication failed")

    async def _subscribe_to_channels(self, ws: WSAssistant, url: str):
        try:
            positions_payload = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": f"{CONSTANTS.WS_POSITIONS_CHANNEL}",
                        "instType": "SWAP"
                    }
                ],
            }
            subscribe_positions_request = WSJSONRequest(positions_payload)

            orders_payload = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": f"{CONSTANTS.WS_ORDERS_CHANNEL}",
                        "instType": "SWAP"
                    }
                ],
            }
            subscribe_orders_request = WSJSONRequest(orders_payload)

            account_payload = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": f"{CONSTANTS.WS_ACCOUNT_CHANNEL}",
                    }
                ],
            }
            subscribe_wallet_request = WSJSONRequest(account_payload)

            await ws.send(subscribe_positions_request)
            await ws.send(subscribe_orders_request)
            await ws.send(subscribe_wallet_request)

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

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue)
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"ping"})
                await websocket_assistant.send(ping_request)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass  # unused

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused
