import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from .lbank_exchange import LbankExchange


class LbankAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: LbankAuth,
        connector: "LbankExchange",
        api_factory: WebAssistantsFactory,
        trading_pairs: List[str]
    ):
        super().__init__()
        self._auth: LbankAuth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs

        self._rest_assistant: Optional[RESTAssistant] = None

        self._current_listening_key: Optional[str] = None
        self._listen_key_initialized_event = asyncio.Event()
        self._last_listen_key_ping_ts: int = 0

    async def _get_listening_key(self) -> str:
        rest_assistant: RESTAssistant = await self._get_rest_assistant()
        try:
            response = await rest_assistant.execute_request(
                url=web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL),
                method=RESTMethod.POST,
                data={"api_key": self._auth.api_key},
                throttler_limit_id=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL,
                is_auth_required=True,
            )
            if response.get("result") is False or "data" not in response:
                err_code: int = response.get("error_code")
                err_msg: str = f"Error Code: {err_code} - {CONSTANTS.ERROR_CODES.get(err_code, '')}."
                raise ValueError(f"Unable to fetch listening key. {err_msg} Response: {response}")
        except asyncio.CancelledError:
            raise
        except ValueError as e:
            self.logger().exception(str(e))
            raise
        except Exception as e:
            self.logger().exception(f"Unexpected error fetching user stream listening key. Error: {str(e)}")
            raise

        return response["data"]

    async def _extend_listening_key(self) -> bool:
        if self._current_listening_key is None:
            self.logger().warning("Listening Key not initialized yet...")
            return False

        rest_assistant: RESTAssistant = await self._api_factory.get_rest_assistant()
        extension_status: bool = False
        try:
            response = await rest_assistant.execute_request(
                url=web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL),
                method=RESTMethod.POST,
                data={"api_key": self._auth.api_key, "subscribeKey": self._current_listening_key},
                throttler_limit_id=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL,
                is_auth_required=True,
                return_err=True,
            )
            extension_status = response.get("result", False)

            if not extension_status:
                err_code: int = response.get("error_code")
                err_msg: str = f"Error Code: {err_code} - {CONSTANTS.ERROR_CODES.get(err_code, '')}."
                raise ValueError(f"Unable to extend validity of listening key. {err_msg} Response: {response}")
        except asyncio.CancelledError:
            raise
        except ValueError as e:
            self.logger().exception(str(e))
        except Exception as e:
            self.logger().exception(f"Unexpected error occurred extending validity of listening key... Error: {str(e)}")

        return extension_status

    async def _manage_listening_key_task_loop(self):
        try:
            while True:
                now = int(self._time() * 1e3)
                if self._current_listening_key is None:
                    self._current_listening_key = await self._get_listening_key()
                    self.logger().info(f"Successfully obtained listening key: {self._current_listening_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = int(self._time() * 1e3)

                if now - self._last_listen_key_ping_ts >= CONSTANTS.LBANK_LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self._extend_listening_key()
                    if not success:
                        self.logger().exception("Unable to extend validity of listening key...")
                        return
                    else:
                        self.logger().info(f"Refreshed listening key: {self._current_listening_key}")
                        self._last_listen_key_ping_ts = int(self._time() * 1e3)
                else:
                    await self._sleep(CONSTANTS.LBANK_LISTEN_KEY_KEEP_ALIVE_INTERVAL)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().exception(f"Unexpected error occurred maintaining listening key. Error: {str(e)}")
        finally:
            self._current_listening_key = None
            self._listen_key_initialized_event.clear()
            self._ws_assistant and await self._ws_assistant.disconnect()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """

        self._manage_listen_key_task = safe_ensure_future(self._manage_listening_key_task_loop())
        await self._listen_key_initialized_event.wait()

        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.LBANK_WSS_URL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            await self._listen_key_initialized_event.wait()

            payload = {"action": "subscribe", "subscribe": "assetUpdate", "subscribeKey": self._current_listening_key}
            subscribe_asset_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await websocket_assistant.send(subscribe_asset_request)

            for trading_pair in self._trading_pairs:
                payload = {
                    "action": "subscribe",
                    "subscribe": "orderUpdate",
                    "subscribeKey": self._current_listening_key,
                    "pair": await self._connector.exchange_symbol_associated_to_pair(trading_pair),
                }
                subscribe_order_request: WSJSONRequest = WSJSONRequest(payload=payload)
                await websocket_assistant.send(subscribe_order_request)

            self.logger().info("Subscribed to user assets and order websocket channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user asset and order updates...")
            raise

    async def _handle_ping_message(self, event_message: Dict[str, Any]):
        try:
            ws: WSAssistant = await self._get_ws_assistant()
            pong_payload = {"action": "pong", "pong": event_message["ping"]}
            pong_request: WSJSONRequest = WSJSONRequest(payload=pong_payload)
            await ws.send(pong_request)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().exception(
                f"Unexpected error occurred sending ping request to user stream connection... Error: {str(e)}",
                exc_info=True,
            )
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0:
            if "ping" in event_message:
                await self._handle_ping_message(event_message)
            if "type" in event_message:
                channel = event_message["type"]
                if channel in [CONSTANTS.LBANK_USER_ORDER_UPDATE_CHANNEL, CONSTANTS.LBANK_USER_BALANCE_UPDATE_CHANNEL]:
                    queue.put_nowait(event_message)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        try:
            while True:
                try:
                    await asyncio.wait_for(
                        super()._process_websocket_messages(websocket_assistant=websocket_assistant, queue=queue),
                        timeout=self._ping_request_interval())
                except asyncio.TimeoutError:
                    payload = {
                        "action": "ping",
                        "ping": str(uuid.uuid4())
                    }
                    ping_request: WSJSONRequest = WSJSONRequest(payload=payload)
                    await websocket_assistant.send(ping_request)
        except ConnectionError as e:
            if "Close code = 1000" in str(e):  # WS closed by server
                self.logger().warning(str(e))
            else:
                raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        self._manage_listen_key_task and self._manage_listen_key_task.cancel()
        self._current_listening_key = None
        self._listen_key_initialized_event.clear()

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _ping_request_interval(self):
        return CONSTANTS.LBANK_WS_PING_REQUEST_INTERVAL
