import asyncio
from collections import (
    OrderedDict,
)
from enum import (
    Enum,
)
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)


class RequestCacheValidationThreshold(Enum):
    FINALIZED = "finalized"
    SAFE = "safe"


class SimpleCache:
    def __init__(self, size: int = 100):
        self._size = size
        self._data: OrderedDict[str, Any] = OrderedDict()

    def cache(self, key: str, value: Any) -> Tuple[Any, Dict[str, Any]]:
        evicted_items = {}
        # If the key is already in the OrderedDict just update it
        # and don't evict any values. Ideally, we could still check to see
        # if there are too many items in the OrderedDict but that may rearrange
        # the order it should be unlikely that the size could grow over the limit
        if key not in self._data:
            while len(self._data) >= self._size:
                k, v = self._data.popitem(last=False)
                evicted_items[k] = v
        self._data[key] = value

        # Return the cached value along with the evicted items at the same time. No
        # need to reach back into the cache to grab the value.
        return value, evicted_items or None

    def get_cache_entry(self, key: str) -> Optional[Any]:
        return self._data[key] if key in self._data else None

    def clear(self) -> None:
        self._data.clear()

    def items(self) -> List[Tuple[str, Any]]:
        return list(self._data.items())

    def pop(self, key: str) -> Optional[Any]:
        if key not in self._data:
            return None

        return self._data.pop(key)

    def popitem(self, last: bool = True) -> Tuple[str, Any]:
        return self._data.popitem(last=last)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    # -- async utility methods -- #

    async def async_await_and_popitem(
        self, last: bool = True, timeout: float = 10.0
    ) -> Tuple[str, Any]:
        start = time.time()
        end_time = start + timeout
        while True:
            await asyncio.sleep(0)
            try:
                return self.popitem(last=last)
            except KeyError:
                now = time.time()
                if now >= end_time:
                    raise asyncio.TimeoutError(
                        "Timeout waiting for item to be available"
                    )
                await asyncio.sleep(min(0.1, end_time - now))
