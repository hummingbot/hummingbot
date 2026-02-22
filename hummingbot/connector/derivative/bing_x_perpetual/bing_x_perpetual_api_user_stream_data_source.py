import asyncio
import logging
import time
from typing import Optional

import hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_utils as utils
import hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_auth import BingXPerpetualAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BingXPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800

    _bausds_logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: BingXPerpetualAuth,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__()
        self._auth: BingXPerpetualAuth = auth
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,
            auth=self._auth)
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_ws_message_sent_timestamp = 0
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0
        self._current_listen_key = None
        self._manage_listen_key_task = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                self._last_ws_message_sent_timestamp = self._time()
                while True:
                    try:
                        seconds_until_next_ping = (CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL -
                                                   (self._time() - self._last_ws_message_sent_timestamp))
                        await asyncio.wait_for(
                            self._process_ws_messages(ws=ws, output=output), timeout=seconds_until_next_ping)
                    except asyncio.TimeoutError:
                        ping_time = self._time()
                        payload = {"ping": int(ping_time * 1e3)}
                        ping_request = WSJSONRequest(payload=payload)
                        await ws.send(request=ping_request)
                        self._last_ws_message_sent_timestamp = ping_time
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                ws and await ws.disconnect()
                await self._sleep(5)

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            # Subscribe to perpetual order updates
            order_payload = {
                "id": "userorder",
                "reqType": "sub",
                "dataType": "ORDER_TRADE_UPDATE"
            }
            subscribe_order_request: WSJSONRequest = WSJSONRequest(payload=order_payload)

            # Subscribe to account/balance/position updates
            account_payload = {
                "id": "useraccount",
                "reqType": "sub",
                "dataType": "ACCOUNT_UPDATE"
            }
            subscribe_account_request: WSJSONRequest = WSJSONRequest(payload=account_payload)

            await ws.send(subscribe_order_request)
            await ws.send(subscribe_account_request)

            self.logger().info("Subscribed to private perpetual channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to user stream channels...",
                exc_info=True
            )
            raise

    async def _process_ws_messages(self, ws: WSAssistant, output: asyncio.Queue):
        self._last_recv_time = self._time()
        async for ws_response in ws.iter_messages():
            data = utils.decompress_ws_message(ws_response.data)
            if isinstance(data, dict):
                event_type = data.get("e")
                if event_type == "ACCOUNT_UPDATE":
                    output.put_nowait(data)
                elif event_type == "ORDER_TRADE_UPDATE":
                    output.put_nowait(data)
                elif data.get("dataType") in ("ORDER_TRADE_UPDATE", "ACCOUNT_UPDATE"):
                    output.put_nowait(data)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _time(self):
        return time.time()

    async def _get_listen_key(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            data = await rest_assistant.execute_request(
                url=web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self._domain),
                method=RESTMethod.POST,
                throttler_limit_id=CONSTANTS.USER_STREAM_PATH_URL,
                headers=self._auth.header_for_authentication()
            )
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(f"Error fetching user stream listen key. Error: {exception}")
        return data["listenKey"]

    async def _ping_listen_key(self) -> bool:
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            data = await rest_assistant.execute_request(
                url=web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self._domain),
                params={"listenKey": self._current_listen_key},
                method=RESTMethod.PUT,
                return_err=True,
                throttler_limit_id=CONSTANTS.USER_STREAM_PATH_URL
            )
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

                if now - self._last_listen_key_ping_ts >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self._ping_listen_key()
                    if not success:
                        self.logger().error("Error occurred renewing listen key ...")
                        break
                    else:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                else:
                    await self._sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
        await self._listen_key_initialized_event.wait()

        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{CONSTANTS.WSS_PRIVATE_URL[self._domain]}?listenKey={self._current_listen_key}"
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        if self._manage_listen_key_task is not None:
            self._manage_listen_key_task.cancel()
        self._current_listen_key = None
        self._listen_key_initialized_event.clear()
        await self._sleep(5)
