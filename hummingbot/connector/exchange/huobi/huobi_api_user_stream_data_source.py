import asyncio
import logging

from typing import Optional

import hummingbot.connector.exchange.huobi.huobi_constants as CONSTANTS

from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth
from hummingbot.connector.exchange.huobi.huobi_utils import build_api_factory
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class HuobiAPIUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_INTERVAL = 30.0  # seconds

    _hausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hausds_logger is None:
            cls._hausds_logger = logging.getLogger(__name__)

        return cls._hausds_logger

    def __init__(self, huobi_auth: HuobiAuth, api_factory: Optional[WebAssistantsFactory] = None):
        self._auth: HuobiAuth = huobi_auth

        self._api_factory = api_factory or build_api_factory()
        self._ws_assistant: Optional[WSAssistant] = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return -1

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _authenticate_client(self):
        """
        Sends an Authentication request to Huobi's WebSocket API Server
        """
        try:
            signed_params = self._auth.add_auth_to_params(
                method="get",
                path_url="/ws/v2",
                is_ws=True,
            )
            auth_request: WSRequest = WSRequest(
                {
                    "action": "req",
                    "ch": "auth",
                    "params": {
                        "authType": "api",
                        "accessKey": signed_params["accessKey"],
                        "signatureMethod": signed_params["signatureMethod"],
                        "signatureVersion": signed_params["signatureVersion"],
                        "timestamp": signed_params["timestamp"],
                        "signature": signed_params["signature"],
                    },
                }
            )
            await self._ws_assistant.send(auth_request)
            resp: WSResponse = await self._ws_assistant.receive()
            auth_response = resp.data
            if auth_response.get("code", 0) != 200:
                raise ValueError(f"User Stream Authentication Fail! {auth_response}")
            self.logger().info("Successfully authenticated to user stream...")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error occurred authenticating websocket connection... Error: {str(e)}", exc_info=True)
            raise

    async def _subscribe_topic(self, topic: str):
        try:
            subscribe_request: WSRequest = WSRequest({"action": "sub", "ch": topic})
            await self._ws_assistant.send(subscribe_request)
            resp: WSResponse = await self._ws_assistant.receive()
            sub_response = resp.data
            if sub_response.get("code", 0) != 200:
                raise ValueError(f"Error subscribing to topic: {topic}")
            self.logger().info(f"Successfully subscribed to {topic}")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Cannot subscribe to user stream topic: {topic}")
            raise

    async def _subscribe_channels(self):
        try:
            await self._subscribe_topic(CONSTANTS.HUOBI_TRADE_DETAILS_TOPIC)
            await self._subscribe_topic(CONSTANTS.HUOBI_ORDER_UPDATE_TOPIC)
            await self._subscribe_topic(CONSTANTS.HUOBI_ACCOUNT_UPDATE_TOPIC)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to private user streams...", exc_info=True)
            raise

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # Initialize Websocket Connection
                self.logger().info(f"Connecting to {CONSTANTS.WS_PRIVATE_URL}")
                await self._get_ws_assistant()
                await self._ws_assistant.connect(ws_url=CONSTANTS.WS_PRIVATE_URL, ping_timeout=self.HEARTBEAT_INTERVAL)

                await self._authenticate_client()
                await self._subscribe_channels()

                async for ws_response in self._ws_assistant.iter_messages():
                    data = ws_response.data
                    if data["action"] == "ping":
                        pong_request = WSRequest(payload={"action": "pong", "data": data["data"]})
                        await self._ws_assistant.send(request=pong_request)
                        continue
                    output.put_nowait(data)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Huobi WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
            finally:
                self._ws_assistant and await self._ws_assistant.disconnect()
                await self._sleep(30.0)
