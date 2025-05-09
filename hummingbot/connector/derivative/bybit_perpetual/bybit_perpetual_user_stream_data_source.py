import asyncio
import time
from typing import List, Optional

from hummingbot.connector.derivative.bybit_perpetual import (
    bybit_perpetual_constants as CONSTANTS,
    bybit_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BybitPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BybitPerpetualAuth,
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
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant(self._domain)
                self._ws_assistants.append(ws)
                await self._subscribe_channels(ws)
                self._last_ws_message_sent_timestamp = self._time()
                while True:
                    try:
                        seconds_until_next_ping = (
                            CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL -
                            (self._time() - self._last_ws_message_sent_timestamp)
                        )
                        await asyncio.wait_for(
                            self._process_ws_messages(ws=ws, output=output), timeout=seconds_until_next_ping)
                    except asyncio.TimeoutError:
                        await self._ping_server(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                await self._sleep(5)

    async def _ping_server(self, ws: WSAssistant):
        ping_time = self._time()
        payload = {
            "op": "ping",
            "args": int(ping_time * 1e3)
        }
        ping_request = WSJSONRequest(payload=payload)
        await ws.send(request=ping_request)
        self._last_ws_message_sent_timestamp = ping_time

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME}"],
            }
            subscribe_orders_request = WSJSONRequest(payload)
            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME}"],
            }
            subscribe_positions_request = WSJSONRequest(payload)
            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME}"],
            }
            subscribe_executions_request = WSJSONRequest(payload)
            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME}"],
            }
            subscribe_wallet_request = WSJSONRequest(payload)

            await ws.send(subscribe_orders_request)
            await ws.send(subscribe_positions_request)
            await ws.send(subscribe_executions_request)
            await ws.send(subscribe_wallet_request)

            self.logger().info("Subscribed to private orders, positions, executions and wallet channels")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to private channels...",
                exc_info=True
            )
            raise

    async def _authenticate_connection(self, ws: WSAssistant):
        """
        Sends the authentication message.
        :param ws: the websocket assistant used to connect to the exchange
        """
        request: WSJSONRequest = WSJSONRequest(
            payload=self._auth.generate_ws_auth_message()
        )
        await ws.send(request)

    async def _process_ws_messages(self, ws: WSAssistant, output: asyncio.Queue):
        async for ws_response in ws.iter_messages():
            data = ws_response.data
            if "op" in data:
                if data.get("op") == "auth":
                    await self._process_ws_auth_msg(data)
                elif data.get("op") == "subscribe":
                    if data.get("success") is False:
                        self.logger().error(
                            "Unexpected error occurred subscribing to private channels...",
                            exc_info=True
                        )
                continue
            topic = data.get("topic")
            channel = ""
            if topic in [
                CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME,
                CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME,
                CONSTANTS.WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME,
                CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME
            ]:
                channel = topic
            else:
                output.put_nowait(data)
            if channel:
                data["channel"] = channel
                output.put_nowait(data)

    async def _process_ws_auth_msg(self, data: dict):
        if not data.get("success"):
            error_msg = f"Private channel authentication failed - {data['ret_msg']}"
            self.logger().error(error_msg)
            raise IOError(error_msg)
        else:
            self.logger().info("Private channel authentication success.")

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_LINEAR_PRIVATE_URLS[domain],
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )
        await self._authenticate_connection(ws)
        return ws

    @staticmethod
    def _get_server_timestamp():
        return web_utils.get_current_server_time()

    def _time(self):
        return time.time()
