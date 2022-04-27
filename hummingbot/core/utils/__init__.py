import cachetools
import errno
import functools
import numpy as np
import socket
import pandas as pd


def async_ttl_cache(ttl: int = 3600, maxsize: int = 1):
    cache = cachetools.TTLCache(ttl=ttl, maxsize=maxsize)

    def decorator(fn):
        @functools.wraps(fn)
        async def memoize(*args, **kwargs):
            key = str((args, kwargs))
            try:
                return cache[key]
            except KeyError:
                cache[key] = await fn(*args, **kwargs)
                return cache[key]

        memoize.cache_clear = lambda: cache.clear()
        return memoize

    return decorator


def map_df_to_str(df: pd.DataFrame) -> pd.DataFrame:
    return df.applymap(lambda x: np.format_float_positional(x, trim="-") if isinstance(x, float) else x).astype(str)


def detect_available_port(starting_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        current_port: int = starting_port
        while current_port < 65535:
            try:
                s.bind(("127.0.0.1", current_port))
                break
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    current_port += 1
                    continue
        return current_port
