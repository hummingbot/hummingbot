import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_stomper as stomper
import hummingbot.connector.exchange.latoken.latoken_web_utils as web_utils
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.latoken.latoken_exchange import LatokenExchange


class LatokenAPIUserStreamDataSource(UserStreamTrackerDataSource):
    # Recommended to Ping/Update listen key to keep connection alive

    def __init__(self,
                 auth: LatokenAuth,
                 trading_pairs: List[str],
                 connector: 'LatokenExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: LatokenAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
        await self._listen_key_initialized_event.wait()

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.ws_url(self._domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        connect_request: WSPlainTextRequest = WSPlainTextRequest(payload=CONSTANTS.WS_CONNECT_MSG, is_auth_required=True)
        await ws.send(connect_request)
        _ = await ws.receive()
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param ws: the websocket assistant used to connect to the exchange
        """
        path_params = {'user': self._current_listen_key}

        msg_subscribe_orders = stomper.subscribe(
            CONSTANTS.ORDERS_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_ORDERS, ack="auto")
        msg_subscribe_trades = stomper.subscribe(
            CONSTANTS.TRADE_UPDATE_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE, ack="auto")
        msg_subscribe_account = stomper.subscribe(
            CONSTANTS.ACCOUNT_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_ACCOUNT, ack="auto")

        _ = await safe_gather(
            websocket_assistant.subscribe(request=WSPlainTextRequest(payload=msg_subscribe_trades)),
            websocket_assistant.subscribe(request=WSPlainTextRequest(payload=msg_subscribe_orders)),
            websocket_assistant.subscribe(request=WSPlainTextRequest(payload=msg_subscribe_account)),
            return_exceptions=True)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        event_type = int(event_message['headers']['subscription'].split('_')[0])
        if event_type == CONSTANTS.SUBSCRIPTION_ID_ACCOUNT or event_type == CONSTANTS.SUBSCRIPTION_ID_ORDERS or event_type == CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE:
            queue.put_nowait(event_message)

    async def _get_listen_key(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            is_auth_required=True,
            return_err=False,
            throttler_limit_id=CONSTANTS.USER_ID_PATH_URL)

        return data["id"]

    async def _ping_listen_key(self) -> bool:
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self._domain),
                method=RESTMethod.GET,
                is_auth_required=True,
                return_err=True,
                throttler_limit_id=CONSTANTS.USER_ID_PATH_URL
            )

            if "id" not in data:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False

        except asyncio.CancelledError:
            raise
        except Exception as exception:
            self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {exception}")
            return False

        return True

    async def _manage_listen_key_task_loop(self):
        try:
            while True:
                now = int(time.time())
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = int(time.time())

                if now - self._last_listen_key_ping_ts >= CONSTANTS.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self._ping_listen_key()
                    if success:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                    else:
                        self.logger().error("Error occurred renewing listen key ...")
                        break
                else:
                    await self._sleep(CONSTANTS.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()
