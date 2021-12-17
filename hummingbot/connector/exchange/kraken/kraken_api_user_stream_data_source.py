#!/usr/bin/env python

import asyncio
import logging
from typing import (
    Dict,
    Optional,
    Any
)

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.connector.exchange.kraken.kraken_order_book import KrakenOrderBook
from hummingbot.connector.exchange.kraken.kraken_utils import (
    build_api_factory
)
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS

MESSAGE_TIMEOUT = 3.0
PING_TIMEOUT = 5.0


class KrakenAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _krausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krausds_logger is None:
            cls._krausds_logger = logging.getLogger(__name__)
        return cls._krausds_logger

    def __init__(self,
                 throttler: AsyncThrottler,
                 kraken_auth: KrakenAuth,
                 api_factory: Optional[WebAssistantsFactory] = None):
        self._throttler = throttler
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant = None
        self._ws_assistant = None
        self._kraken_auth: KrakenAuth = kraken_auth
        self._current_auth_token: Optional[str] = None
        super().__init__()

    @property
    def order_book_class(self):
        return KrakenOrderBook

    @property
    def last_recv_time(self):
        if self._ws_assistant is None:
            return 0
        else:
            return self._ws_assistant.last_recv_time

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def get_auth_token(self) -> str:
        api_auth: Dict[str, Any] = self._kraken_auth.generate_auth_dict(uri=CONSTANTS.GET_TOKEN_PATH_URL)

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.GET_TOKEN_PATH_URL}"

        request = RESTRequest(
            method=RESTMethod.POST,
            url=url,
            headers=api_auth["headers"],
            data=api_auth["postDict"]
        )
        rest_assistant = await self._get_rest_assistant()

        async with self._throttler.execute_task(CONSTANTS.GET_TOKEN_PATH_URL):
            response = await rest_assistant.call(request=request, timeout=100)
            if response.status != 200:
                raise IOError(f"Error fetching Kraken user stream listen key. HTTP status is {response.status}.")

            try:
                response_json: Dict[str, Any] = await response.json()
            except Exception:
                raise IOError(f"Error parsing data from {url}.")

            err = response_json["error"]
            if "EAPI:Invalid nonce" in err:
                self.logger().error(f"Invalid nonce error from {url}. " +
                                    "Please ensure your Kraken API key nonce window is at least 10, " +
                                    "and if needed reset your API key.")
                raise IOError({"error": response_json})

            return response_json["result"]["token"]

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                async with self._throttler.execute_task(CONSTANTS.WS_CONNECTION_LIMIT_ID):
                    ws: WSAssistant = await self._api_factory.get_ws_assistant()
                    await ws.connect(ws_url=CONSTANTS.WS_AUTH_URL, ping_timeout=PING_TIMEOUT)

                    if self._current_auth_token is None:
                        self._current_auth_token = await self.get_auth_token()

                    for subscription_type in ["openOrders", "ownTrades"]:
                        subscribe_request: WSRequest = WSRequest({
                            "event": "subscribe",
                            "subscription": {
                                "name": subscription_type,
                                "token": self._current_auth_token
                            }
                        })
                        await ws.send(subscribe_request)

                    async for ws_response in ws.iter_messages():
                        msg = ws_response.data
                        if not (type(msg) is dict and "event" in msg.keys() and
                                msg["event"] in ["heartbeat", "systemStatus", "subscriptionStatus"]):
                            output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Kraken WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                self._current_auth_token = None
                await asyncio.sleep(30.0)
            finally:
                if ws is not None:
                    await ws.disconnect()
