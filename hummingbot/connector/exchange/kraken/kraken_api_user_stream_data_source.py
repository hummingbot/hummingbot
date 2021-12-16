#!/usr/bin/env python

import asyncio
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    Any
)
import time

import aiohttp
import ujson
import websockets

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.connector.exchange.kraken.kraken_order_book import KrakenOrderBook
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

    def __init__(self, throttler: AsyncThrottler, kraken_auth: KrakenAuth):
        self._throttler = throttler
        self._kraken_auth: KrakenAuth = kraken_auth
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._current_auth_token: Optional[str] = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def order_book_class(self):
        return KrakenOrderBook

    @property
    def last_recv_time(self):
        return self._last_recv_time

    async def get_auth_token(self) -> str:
        api_auth: Dict[str, Any] = self._kraken_auth.generate_auth_dict(uri=CONSTANTS.GET_TOKEN_PATH_URL)

        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.GET_TOKEN_PATH_URL}"

        client: aiohttp.ClientSession = await self._http_client()

        response_coro = client.request(
            method="POST",
            url=url,
            headers=api_auth["headers"],
            data=api_auth["postDict"],
            timeout=100
        )

        async with self._throttler.execute_task(CONSTANTS.GET_TOKEN_PATH_URL):
            async with response_coro as response:
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
                    ws = await websockets.connect(CONSTANTS.WS_AUTH_URL)
                    if self._current_auth_token is None:
                        self._current_auth_token = await self.get_auth_token()

                    for subscription_type in ["openOrders", "ownTrades"]:
                        subscribe_request: Dict[str, Any] = {
                            "event": "subscribe",
                            "subscription": {
                                "name": subscription_type,
                                "token": self._current_auth_token
                            }
                        }
                        await ws.send(ujson.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        self._last_recv_time = time.time()

                        diff_msg = ujson.loads(raw_msg)
                        output.put_nowait(diff_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Kraken WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                self._current_auth_token = None
                await asyncio.sleep(30.0)
            finally:
                if ws is not None:
                    await ws.close()

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None or self._shared_client.closed:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT)
                    if (("heartbeat" not in msg and
                         "systemStatus" not in msg and
                         "subscriptionStatus" not in msg)):
                        yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        finally:
            await ws.close()

    async def stop(self):
        if self._shared_client is not None and not self._shared_client.closed:
            await self._shared_client.close()
