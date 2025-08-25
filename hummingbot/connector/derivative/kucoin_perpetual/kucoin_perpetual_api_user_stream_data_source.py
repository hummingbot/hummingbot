import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.derivative.kucoin_perpetual import (
    kucoin_perpetual_constants as CONSTANTS,
    kucoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_auth import KucoinPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_derivative import KucoinPerpetualDerivative


class KucoinPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'KucoinPerpetualDerivative',
        auth: KucoinPerpetualAuth,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._connector = connector
        self._trading_pairs = trading_pairs
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_listen_key_ping_ts = None

        self._manage_listen_key_task = None
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()

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
                    url=web_utils.wss_private_url(self._domain), output=output
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
                await self._subscribe_to_channels(ws, url, self._trading_pairs)
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
        rest_assistant = await self._api_factory.get_rest_assistant()
        connection_info = await rest_assistant.execute_request(
            url=web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PRIVATE_WS_DATA_PATH_URL, domain=self._domain),
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.PRIVATE_WS_DATA_PATH_URL,
            is_auth_required=True,
        )

        ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
        self._ping_interval = int(connection_info["data"]["instanceServers"][0]["pingInterval"]) * 0.8 * 1e-3
        message_timeout = int(connection_info["data"]["instanceServers"][0]["pingTimeout"]) * 0.8 * 1e-3
        token = connection_info["data"]["token"]

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=f"{ws_url}?token={token}", ping_timeout=self._ping_interval, message_timeout=message_timeout)
        return ws

    async def _subscribe_to_channels(self, ws: WSAssistant, url: str, trading_pairs: List[str]):
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in trading_pairs
            ]
            symbols_str = ",".join(symbols)

            order_change_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": CONSTANTS.WS_TRADES_TOPIC,
                "privateChannel": True,
                "response": False,
            }
            subscribe_orders_request = WSJSONRequest(order_change_payload)
            position_change_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": f"{CONSTANTS.WS_POSITION_CHANGE_TOPIC}:{symbols_str}",
                "privateChannel": True,
                "response": False,
            }
            subscribe_positions_request = WSJSONRequest(position_change_payload)

            wallet_change_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": CONSTANTS.WS_WALLET_INFO_TOPIC,
                "privateChannel": True,
                "response": False,
            }
            subscribe_wallet_request = WSJSONRequest(wallet_change_payload)

            await ws.send(subscribe_orders_request)
            await ws.send(subscribe_positions_request)
            await ws.send(subscribe_wallet_request)

            self.logger().info(
                f"Subscribed to private account and orders channels {url}..."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Unexpected error occurred subscribing to order book trading and delta streams {url}..."
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await asyncio.wait_for(super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue),
                    timeout=CONSTANTS.WS_CONNECTION_TIME_INTERVAL)
            except asyncio.TimeoutError:
                payload = {
                    "id": web_utils.next_message_id(),
                    "type": "ping",
                }
                ping_request = WSJSONRequest(payload=payload)
                self._last_ws_message_sent_timestamp = self._time()
                await websocket_assistant.send(request=ping_request)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass  # unused

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused
