import time
import asyncio
import logging
from typing import (
    Any,
    AsyncIterable,
    List,
    Optional,
)

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .coinzoom_constants import Constants
from .coinzoom_auth import CoinzoomAuth
from .coinzoom_utils import CoinzoomAPIError
from .coinzoom_websocket import CoinzoomWebsocket


class CoinzoomAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, throttler: AsyncThrottler, coinzoom_auth: CoinzoomAuth, trading_pairs: Optional[List[str]] = []):
        self._throttler: AsyncThrottler = throttler
        self._coinzoom_auth: CoinzoomAuth = coinzoom_auth
        self._ws: CoinzoomWebsocket = None
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _ws_request_balances(self):
        return await self._ws.request(Constants.WS_METHODS["USER_BALANCE"])

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """

        try:
            self._ws = CoinzoomWebsocket(throttler=self._throttler, auth=self._coinzoom_auth)

            await self._ws.connect()

            await self._ws.subscribe({Constants.WS_SUB["USER_ORDERS_TRADES"]: {}})

            event_methods = [
                Constants.WS_METHODS["USER_ORDERS"],
                # We don't need to know about pending cancels
                # Constants.WS_METHODS["USER_ORDERS_CANCEL"],
            ]

            async for msg in self._ws.on_message():
                self._last_recv_time = time.time()

                msg_keys = list(msg.keys()) if msg is not None else []

                if not any(ws_method in msg_keys for ws_method in event_methods):
                    continue
                yield msg
        except Exception as e:
            raise e
        finally:
            await self._ws.disconnect()
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                async for msg in self._listen_to_orders_trades_balances():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except CoinzoomAPIError as e:
                self.logger().error(e.error_payload.get('error'), exc_info=True)
                raise
            except Exception:
                self.logger().error(
                    f"Unexpected error with {Constants.EXCHANGE_NAME} WebSocket connection. "
                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)
