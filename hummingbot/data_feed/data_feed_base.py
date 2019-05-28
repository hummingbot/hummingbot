import aiohttp
import logging
import asyncio
from typing import (
    Optional,
    Dict,
)

from hummingbot.logger import HummingbotLogger


class DataFeedBase:
    dfb_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dfb_logger is None:
            cls.dfb_logger = logging.getLogger(__name__)
        return cls.dfb_logger

    def __init__(self):
        self._ready_event = asyncio.Event()
        self._shared_client: Optional[aiohttp.ClientSession] = None

    @property
    def name(self):
        raise NotImplementedError

    @property
    def price_dict(self) -> Dict[str, float]:
        raise NotImplementedError

    def get_price(self, asset: str) -> float:
        raise NotImplementedError

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def get_ready(self):
        try:
            if not self._ready_event.is_set():
                await self._ready_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error while waiting for data feed to get ready.",
                                exc_info=True)

    def start(self):
        pass

    def stop(self):
        pass
