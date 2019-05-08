import logging
import asyncio
from typing import (
    Optional,
    Dict,
)


class DataFeedBase:
    dfb_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls.dfb_logger is None:
            cls.dfb_logger = logging.getLogger(__name__)
        return cls.dfb_logger

    def __init__(self):
        self._ready_event = asyncio.Event()

    @property
    def price_dict(self) -> Dict[str, float]:
        raise NotImplementedError

    def get_price(self, asset: str) -> float:
        raise NotImplementedError

    async def get_ready(self):
        try:
            if not self._ready_event.is_set():
                await self._ready_event.wait()
        except Exception as e:
            self.logger().error(e, exc_info=True)

