import asyncio
import hashlib
import traceback
from datetime import datetime
from typing import Any, List

import jsonpickle


def generate_hash(input: Any) -> str:
    return generate_hashes([input])[0]


def generate_hashes(inputs: List[Any]) -> List[str]:
    hashes = []
    salt = datetime.now()

    for input in inputs:
        serialized = jsonpickle.encode(input, unpicklable=True)
        hasher = hashlib.md5()
        target = f"{salt}{serialized}".encode("utf-8")
        hasher.update(target)
        hash = hasher.hexdigest()

        hashes.append(hash)

    return hashes


def convert_hb_trading_pair_to_market_name(trading_pair: str) -> str:
    return trading_pair.replace("-", "/")


def convert_market_name_to_hb_trading_pair(market_name: str) -> str:
    return market_name.replace("/", "-")


def automatic_retry_with_timeout(retries=0, delay=0, timeout=None):
    def decorator(function):
        async def wrapper(*args, **kwargs):
            errors = []

            for i in range(retries + 1):
                try:
                    result = await asyncio.wait_for(function(*args, **kwargs), timeout=timeout)

                    return result
                except Exception as e:
                    tb_str = traceback.format_exception(type(e), value=e, tb=e.__traceback__)
                    errors.append(''.join(tb_str))

                    if i < retries:
                        await asyncio.sleep(delay)

            error_message = f"Function failed after {retries} attempts. Here are the errors:\n" + "\n".join(errors)

            raise Exception(error_message)

        wrapper.original = function

        return wrapper

    return decorator


class AsyncLock:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._lock.release()
