import time
import asyncio
import logging

from typing import Optional, List, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

from .client.asyncio import AsyncIdexClient
from .idex_auth import IdexAuth
from .utils import get_markets


class IdexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        cls._logger = cls._logger or logging.getLogger(__name__)
        return cls._logger

    def __init__(self, idex_auth: IdexAuth, trading_pairs: Optional[List[str]] = []):
        self._idex_auth = idex_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super(IdexAPIUserStreamDataSource, self).__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        try:
            client = AsyncIdexClient()
            async for message in client.subscribe(
                    subscriptions=["orders", "trades", "balances"],
                    markets=(await get_markets()),
                    auth=self._idex_auth):
                # Will raise ValueError if message will not able to handle
                yield message
                self._last_recv_time = time.time()
        finally:
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async for msg in self._listen_to_orders_trades_balances():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Idex AsyncIdexClient connection. Retrying after 30 seconds...",
                    exc_info=True
                )
                await asyncio.sleep(30.0)
