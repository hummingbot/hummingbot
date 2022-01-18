#!/usr/bin/env python

import asyncio
import logging
from typing import Any, Dict, List, Optional

import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BitmartAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 10.0
    PING_TIMEOUT = 2.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    def __init__(
        self,
        bitmart_auth: BitmartAuth,
        throttler: Optional[AsyncThrottler] = None,
        trading_pairs: Optional[List[str]] = None,
        api_factory: Optional[WebAssistantsFactory] = None
    ):
        super().__init__()
        self._api_factory = api_factory or bitmart_utils.build_api_factory()
        self._rest_assistant = None
        self._ws_assistant = None
        self._bitmart_auth: BitmartAuth = bitmart_auth
        self._trading_pairs = trading_pairs or []
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._throttler = throttler or self._get_throttler_instance()

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant is not None:
            return self._ws_assistant.last_recv_time
        else:
            return 0

    async def _get_ws_assistant(self) -> RESTAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _authenticate(self, ws: WSAssistant):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = self._bitmart_auth.get_ws_auth_payload(bitmart_utils.get_ms_timestamp())
            ws_message: WSRequest = WSRequest(auth_payload)

            await ws.send(ws_message)
            ws_response = await ws.receive()

            auth_resp: Dict[str, Any] = ws_response.data

            if "errorCode" in auth_resp.keys():
                self.logger().error(f"WebSocket login errored with message: {auth_resp['errorMessage']}",
                                    exc_info=True)
                raise ConnectionError
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Error occurred when authenticating to user stream.", exc_info=True)
            raise

    async def _subscribe_to_channels(self, ws: WSAssistant):
        """
        Subscribes to Private User Channels
        """
        try:
            # BitMart WebSocket API currently offers only spot/user/order private channel.
            for trading_pair in self._trading_pairs:
                ws_message: WSRequest = WSRequest({
                    "op": "subscribe",
                    "args": [f"spot/user/order:{bitmart_utils.convert_to_exchange_trading_pair(trading_pair)}"]
                })
                await ws.send(ws_message)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Error occured during subscribing to Bitmart private channels.", exc_info=True)
            raise

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                try:
                    await ws.connect(ws_url=CONSTANTS.WSS_URL,
                                     message_timeout=self.MESSAGE_TIMEOUT,
                                     ping_timeout=self.PING_TIMEOUT)
                except RuntimeError:
                    self.logger().info("BitMart WebSocket already connected.")
                self.logger().info("Authenticating to User Stream...")
                await self._authenticate(ws)
                self.logger().info("Successfully authenticated to User Stream.")
                await self._subscribe_to_channels(ws)
                self.logger().info("Successfully subscribed to all Private channels.")

                while True:
                    try:
                        async for raw_msg in ws.iter_messages():
                            messages = raw_msg.data
                            if messages is None:
                                continue

                            if "errorCode" in messages.keys() or \
                               "data" not in messages.keys() or \
                               "table" not in messages.keys():
                                # Error/Unrecognized response from "depth400" channel
                                continue

                            if messages["table"] != "spot/user/order":
                                # Not a trade or order message
                                continue

                            output.put_nowait(messages)

                        break
                    except asyncio.exceptions.TimeoutError:
                        # Check whether connection is really dead
                        await ws.ping()
            except asyncio.CancelledError:
                raise
            except asyncio.exceptions.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Going to reconnect...")
                await ws.disconnect()
                await asyncio.sleep(30.0)
            except Exception:
                self.logger().error(
                    "Unexpected error with BitMart WebSocket connection. Retrying after 30 seconds...",
                    exc_info=True
                )
                await ws.disconnect()
                await asyncio.sleep(30.0)
