import asyncio
from typing import Dict


class DataFeedBase:
    def __init__(self):
        self._ready = False

    @property
    def price_dict(self) -> Dict[str, float]:
        raise NotImplementedError

    def get_price(self, asset: str) -> float:
        raise NotImplementedError

    async def get_ready(self):
        while True:
            if not self._ready:
                await asyncio.sleep(1)
                continue
            else:
                return

