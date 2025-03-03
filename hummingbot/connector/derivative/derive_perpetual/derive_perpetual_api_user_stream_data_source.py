import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.derive_perpetual import (
    derive_perpetual_constants as CONSTANTS,
    derive_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth import DerivePerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future

# from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative import DerivePerpetualDerivative


class DerivePerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    WS_HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: DerivePerpetualAuth,
            trading_pairs: List[str],
            connector: 'DerivePerpetualDerivative',
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

        if message["id"] == id:
            if "result" not in message:
                self.logger().error("Error authenticating the private websocket connection")
                raise IOError("Private websocket connection authentication failed")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange's user stream.
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=self.WS_HEARTBEAT_TIME_INTERVAL)
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        subaccount_id = self._connector._sub_id
        try:
            await self._authenticate(websocket_assistant)  # Authenticate once

            # Define all subscription payloads
            subscription_payloads = [
                {
                    "method": channel,
                    "params": {"subaccount_id": int(subaccount_id)}
                }
                for channel in [CONSTANTS.WS_ACCOUNT_CHANNEL, CONSTANTS.WS_POSITIONS_CHANNEL]
            ] + [
                {
                    "method": "subscribe",
                    "params": {"channels": [
                        CONSTANTS.WS_ORDERS_CHANNEL.format(subaccount_id=subaccount_id),
                        CONSTANTS.WS_TRADES_CHANNEL.format(subaccount_id=subaccount_id)
                    ]}
                }
            ]

            # Send all subscription requests in parallel
            await asyncio.gather(*[
                websocket_assistant.send(WSJSONRequest(payload))
                for payload in subscription_payloads
            ])
            self.logger().info("Subscribed to private account, position and orders channels...")
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
        elif "params" in event_message or "result" in event_message:
            if "result" in event_message:
                if "status" in event_message["result"]:
                    return
                if "id" in event_message and event_message["id"] is not None:
                    return
                queue.put_nowait(event_message)
            elif "params" in event_message and "channel" in event_message["params"]:
                if CONSTANTS.USER_ORDERS_ENDPOINT_NAME in event_message["params"]["channel"] or \
                        CONSTANTS.USEREVENT_ENDPOINT_NAME in event_message["params"]["channel"]:
                    queue.put_nowait(event_message["params"])

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
