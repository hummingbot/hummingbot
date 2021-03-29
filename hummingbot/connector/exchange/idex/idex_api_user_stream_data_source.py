import asyncio
import time
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    List,
)

import json
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.connector.exchange.idex.idex_resolve import get_idex_ws_feed
from hummingbot.connector.exchange.idex.idex_order_book import IdexOrderBook
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from .idex_auth import IdexAuth
from .idex_utils import DEBUG


class IdexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    PING_TIMEOUT = 10.0
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        cls._logger = cls._logger or logging.getLogger(__name__)
        return cls._logger

    def __init__(self, idex_auth: IdexAuth, trading_pairs: Optional[List[str]] = [], domain: str = "eth"):
        self._idex_auth = idex_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self.sub_token: str = ""
        self._domain = domain
        super(IdexAPIUserStreamDataSource, self).__init__()

    @property
    def order_book_class(self):
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return IdexOrderBook

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Path subscription notation: wss://websocket-{blockchain}.idex.io/v1/{market}@{subscription}_{option}
        Example for 15m market tickers from ETH-USDC
        :blockchain: eth
        :option: 15m
        :subcription: ticker
        :market: ETH-USDC
                Example subscribe JSON:
        {
            "method": "subscribe",
            "markets": ["ETH-USDC", "IDEX-ETH"],
            "subscriptions": [
                "tickers",
                "trades"
            ]
        }
        """

        while True:
            idex_ws_feed = get_idex_ws_feed()
            if DEBUG:
                self.logger().info(f"Opening new connection to ws: {idex_ws_feed}")
            try:
                async with websockets.connect(idex_ws_feed) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, any] = {
                        "method": "subscribe",
                        "markets": self._trading_pairs,

                        "subscriptions": ["orders", "balances"],
                    }
                    self.sub_token = await self._idex_auth.fetch_ws_token()
                    subscribe_request.update({"token": self.sub_token})
                    # send sub request
                    await ws.send(json.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = json.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if DEBUG:
                            self.logger().info(f'<<<<< ws msg: {msg}')
                        if msg_type is None:
                            raise ValueError(f"idex Websocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"idex Websocket received error message - {msg['data']}")
                        elif msg_type in ["balances", "orders"]:
                            output.put_nowait(msg)
                        elif msg_type in ["ping"]:
                            # server sends ping every 3 minutes, must receive a pong within a 10 minute period
                            safe_ensure_future(ws.pong())
                        elif msg_type in ["subscriptions"]:
                            self.logger().info(f"subscription msg received: {msg}")
                        else:
                            raise ValueError(f"Unrecognized idex Websocket message received - {msg}")
                        await asyncio.sleep(0)
            except asyncio.CancelledError as e:
                if DEBUG:
                    self.logger().exception("<<<< listen_for_user_stream received CancelledError...")
                raise e
            except Exception:
                self.logger().error("Unexpected error with Idex WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        self._last_recv_time = time.time()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            if DEBUG:
                self.logger().warning("WebSocket connection was closed. Going to reconnect...")
            return
        finally:
            await ws.close()
