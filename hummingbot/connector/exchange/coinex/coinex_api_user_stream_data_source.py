#!/usr/bin/env python

import asyncio
import logging
import time
from typing import Any, AsyncIterable, Dict, List, Optional

import ujson
import websockets
from async_timeout import timeout
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.connector.exchange.coinex.coinex_utils import (
    convert_to_exchange_trading_pair, split_trading_pair)
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.user_stream_tracker_data_source import \
    UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.healthcheck import healthcheck
from hummingbot.logger import HummingbotLogger
from websockets.legacy.client import Connect as WSConnectionContext

COINEX_REST_URL = "https://api.coinex.com/v1"
COINEX_WS_FEED = "wss://socket.coinex.com"
MAX_RETRIES = 20
HTTP_TIMEOUT = 10.0
NaN = float("nan")


class CoinexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    PING_TIMEOUT = 61.0
    PING_INTERVAL = 55.00

    _cbpausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpausds_logger is None:
            cls._cbpausds_logger = logging.getLogger(__name__)
        return cls._cbpausds_logger

    def __init__(self, coinex_auth: CoinexAuth, trading_pairs: Optional[List[str]] = []):
        self._coinex_auth: CoinexAuth = coinex_auth
        self._trading_pairs = trading_pairs
        self._last_recv_time: float = 0
        self._ping_task: Optional[asyncio.Task] = None
        self._last_nonce: int = int(time.time() * 1e3)
        self._websocket_connection: Optional[WSConnectionContext] = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @property
    def ping_task(self) -> Optional[asyncio.Task]:
        return self._ping_task

    def get_nonce(self) -> int:
        now_ms: int = int(time.time() * 1e3)
        if now_ms <= self._last_nonce:
            now_ms = self._last_nonce + 1
        self._last_nonce = now_ms
        return now_ms

    async def get_ws_connection(self) -> WSConnectionContext:
        self.logger().debug("Connecting Websocket")
        # TODO: Review / cleanup using constants
        return WSConnectionContext(COINEX_WS_FEED, ping_interval=None, ping_timeout=None)

    async def _subscribe_topic(self, topic: str) -> None:
        """
        See:
        https://github.com/coinexcom/coinex_exchange_api/wiki/051asset
        https://github.com/coinexcom/coinex_exchange_api/wiki/052order
        """
        self.logger().debug(f"Trading pairs passed in: {self._trading_pairs}")
        params = [tp.split('-') for tp in self._trading_pairs]
        self.logger().debug(f"SUBSCRIBE PARAMS: {list(sorted(set([c for tp in params for c in tp])))}")
        if topic == "asset":
            subscribe_request: Dict[str, Any] = {
                "method": "asset.subscribe",
                "params": list(sorted(set([c for tp in params for c in tp]))),  # Remove duplicate currencies
                "id": self.get_nonce()
            }
            self.logger().debug("Sending Asset Subscribe Request")
            await self._websocket_connection.send(ujson.dumps(subscribe_request))
            self.logger().debug("Received Asset Subscribe Response")
        else:
            subscribe_request = {
                "method": "order.subscribe",
                "params": [convert_to_exchange_trading_pair(tp) for tp in self._trading_pairs],
                "id": self.get_nonce()
            }
            self.logger().debug("Sending Order Subscribe Request")
            await self._websocket_connection.send(ujson.dumps(subscribe_request))
            self.logger().debug("Received Order Subscribe Response")

    async def _authenticate_client(self) -> None:
        """
        See: https://github.com/coinexcom/coinex_exchange_api/wiki/050id_verification
        """
        auth_list: List[Any] = self._coinex_auth.generate_auth_list()

        auth_request: Dict[str, Any] = {
            "method": "server.sign",
            "params": auth_list,
            "id": self.get_nonce()
        }
        self.logger().debug("Sending Auth Request")
        await self._websocket_connection.send(ujson.dumps(auth_request))
        self.logger().debug("Received Auth Response")
        resp = await self._websocket_connection.recv()
        msg = ujson.loads(resp)
        if msg.get("result", None):
            self.logger().debug("Auth'ed Client")

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> None:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        # Our healthcheck
        healthcheck_last: float = time.time()
        await healthcheck("account", time.time())
        while True:
            try:
                # Initialize Websocket Connection
                self.logger().info("Initialize Websocket Connection")
                async with (await self.get_ws_connection()) as ws:
                    self._websocket_connection = ws

                    # Authentication
                    self.logger().info("Authing Client")
                    await self._authenticate_client()

                    # Subscribe to Topic(s)
                    self.logger().info("Subscribing Topics")
                    await self._subscribe_topic("asset")  # balance(s)
                    await self._subscribe_topic("order")  # order(s)
                    # TODO: We need to handle the deals update too I think....

                    # Ping / pong loop
                    self.logger().info("Setting Up Ping / Pong Loop")
                    if self._ping_task is None:
                        self._ping_task = safe_ensure_future(self._ping_loop())
                        self.logger().info("Setup Ping / Pong Loop")
                    self.logger().info("Waiting For Messages")
                    async for message in self._inner_messages():
                        # self.logger().debug(f"Message Received: {message}")
                        # TODO: Review - Do we want to handle some cleanup here? Like below to match orderbooks?
                        error = message.get("error", None)
                        result = message.get("result", None)
                        method = message.get("method", None)
                        # Check for errors and results in message (we want to continue loop as these can be ignored)
                        if error is not None or result is not None:
                            if error is not None:
                                self.logger().error(f"Error in message: {message}")
                                continue  # TODO: Do we want to continue or raise?
                            elif "status" in result and result["status"] == "success":
                                self.logger().debug(f"Result was successful: {message}")
                                continue
                            elif result == "pong":
                                self.logger().debug(f"Received pong: {message}")
                                continue
                            else:
                                self.logger().info(f"Weird, not something we handle: {message}")
                        # We only want to pass useful messages to the event loop.
                        elif method is not None:
                            output.put_nowait(message)
                            if (time.time() - healthcheck_last) >= 3.0:
                                await healthcheck("account", time.time())
                                healthcheck_last = time.time()
                        else:
                            raise ValueError(f"Unrecognized CoinEx Websocket message received - {message}")
            except asyncio.CancelledError:
                raise
            except websockets.exceptions.ConnectionClosed as e:
                self.logger().error(f"Websocket connection closed: {e}")
            except websockets.exceptions.ConnectionClosedError as e:
                self.logger().error(f"Websocket had a connection issue: {e}")
            except IOError as e:
                self.logger().error(e, exc_info=True)
            except Exception as e:
                self.logger().error(f"Unexpected error occurred! {e} {message}", exc_info=True)
            finally:
                if self._websocket_connection is not None:
                    await self._websocket_connection.close()
                    self._websocket_connection = None
                if self._ping_task is not None:
                    self._ping_task.cancel()
                    self._ping_task = None

    async def _ping_loop(self) -> None:
        self.logger().info("Called Ping Loop")
        while True:
            # TODO: Flagged for review and cleanup
            try:
                ping_msg: Dict[str, Any] = {
                    "method": "server.ping",
                    "params": [],
                    "id": self.get_nonce(),
                }
                self.logger().info("Sending Ping")
                await self._websocket_connection.send(ujson.dumps(ping_msg))
                self.logger().info("Pong Received")
                self.logger().info("Waiting For Next Ping")
                await asyncio.sleep(self.PING_INTERVAL)
            except asyncio.TimeoutError:
                self.logger().warning("Ping timeout, going to reconnect...")
                break
            except asyncio.CancelledError:
                self.logger().error("Ping loop has been cancelled.")
                raise
            except Exception as e:
                self.logger().error(f"Ping loop had unhandled exception: {e}")
                raise

    # TODO: Review how to properly exit from AsyncIterable
    async def _inner_messages(self) -> AsyncIterable[dict]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        while True:
            try:
                self.logger().debug("In Message Loop, Awaiting")
                raw_msg = await self._websocket_connection.recv()
                self.logger().debug(f"Loop Message Received Yielding: {raw_msg}")
                self._last_recv_time = time.time()
                message = ujson.loads(raw_msg)
                yield message
            except asyncio.TimeoutError:
                self.logger().warning("Userstream websocket timeout, going to reconnect...")
                return
