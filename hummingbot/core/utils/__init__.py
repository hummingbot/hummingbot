import cachetools
import functools
import pandas as pd
import numpy as np


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
        return memoize

    return decorator


def map_df_to_str(df: pd.DataFrame) -> pd.DataFrame:
    return df.applymap(lambda x: np.format_float_positional(x, trim="-") if isinstance(x, float) else x).astype(str)
