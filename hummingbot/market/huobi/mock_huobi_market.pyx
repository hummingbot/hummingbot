import aiohttp
import asyncio
from async_timeout import timeout
import conf
from datetime import datetime
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import pandas as pd
import re
import time
from typing import (
    Any,
    AsyncIterable,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple
)
import ujson

from hummingbot.market.huobi.huobi_market import HuobiMarket

cdef class MockHuobiMarket(HuobiMarket):

    def __init__(self,
                 huobi_api_key: str,
                 huobi_secret_key: str,
                 client,
                 symbols: Optional[List[str]] = None,
                 ):
        print(huobi_api_key, huobi_secret_key, client, symbols)
        super().__init__(huobi_api_key, huobi_secret_key, symbols=symbols)
        self._client = client
    
    async def _http_client(self):
        return await self.client
 