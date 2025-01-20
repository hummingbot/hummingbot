import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS, derive_web_utils as web_utils
from hummingbot.connector.exchange.derive.derive_auth import DeriveAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future

# from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.derive.derive_exchange import DeriveExchange


class DeriveAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    WS_HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: DeriveAuth,
            trading_pairs: List[str],
            connector: 'DeriveExchange',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):

        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
        self._trading_pairs: List[str] = trading_pairs

        self.token = None

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _authenticate(self, ws: WSAssistant):
        """
        Authenticates user to websocket
        """
        auth_payload: List[str] = self._auth.get_ws_auth_payload()
        id = str(web_utils.utc_now_ms())
        payload = {
            "method": "public/login",
            "params": auth_payload,
            "id": id,
        }
        login_request: WSJSONRequest = WSJSONRequest(payload=payload)
        await ws.send(login_request)
        response: WSResponse = await ws.receive()
        message = response.data

        while True:
            if message["id"] == id:
                if "result" not in message:
                    self.logger().error("Error authenticating the private websocket connection")
                    raise IOError("Private websocket connection authentication failed")
                break

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=self.WS_HEARTBEAT_TIME_INTERVAL)
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        subaccount_id = self._connector._sub_id
        try:
            orders_change_payload = {
                "method": "subscribe",
                "params": {
                    "channels": [f"{subaccount_id}.orders"],
                }
            }
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(
                payload=orders_change_payload)

            trades_payload = {
                "method": "subscribe",
                "params": {
                    "channels": [f"{subaccount_id}.trades"],
                }
            }
            subscribe_trades_request: WSJSONRequest = WSJSONRequest(
                payload=trades_payload)
            await self._authenticate(websocket_assistant)
            await websocket_assistant.send(subscribe_order_change_request)
            await websocket_assistant.send(subscribe_trades_request)

            self.logger().info("Subscribed to private order and trades changes channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message["error"]["message"]
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}."
            })
        elif event_message.get("params") is not None:
            if "channel" in event_message["params"]:
                if CONSTANTS.USER_ORDERS_ENDPOINT_NAME in event_message["channel"] or \
                        CONSTANTS.USEREVENT_ENDPOINT_NAME in event_message["channel"]:
                    queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant,):
        try:
            while True:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                await self._authenticate(websocket_assistant)
                await websocket_assistant.send(ping_request)
        except Exception as e:
            self.logger().debug(f'ping error {e}')

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue)
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await websocket_assistant.send(ping_request)
