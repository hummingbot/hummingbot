import enum
import logging
from typing import Dict, Any, List, Optional
import hummingbot.market.eterbase.eterbase_constants as constants
from hummingbot.market.eterbase.eterbase_auth import EterbaseAuth

import aiohttp
import asyncio
import json
from threading import Thread

logger = logging.getLogger(__name__)
shared_client = None

marketid_map = None

API_CALL_TIMEOUT = 10.0

async def _http_client(loop: Optional = None) -> aiohttp.ClientSession:
    """
    :returns: Shared client session instance
    """
    # calling API from different thread
    if loop!=None:
        return aiohttp.ClientSession(loop=loop)

    # calling API fro main thread
    global shared_client
    if shared_client is None:
        shared_client = aiohttp.ClientSession()
    return shared_client

async def api_request(http_method: str,
                       path_url: str = None,
                       url: str = None,
                       data: Optional[Dict[str, Any]] = None,
                       auth: Optional[EterbaseAuth] = None,
                       loop: Optional = None) -> Dict[str, Any]:
    """
    A wrapper for submitting API requests to Eterbase
    :returns: json data from the endpoints
    """
    assert path_url is not None or url is not None

    url = f"{constants.REST_URL}{path_url}" if url is None else url
    data_str = None if data is None else json.dumps(data)

    headers = None
    if auth != None:
        headers = auth.get_headers(http_method, url, data_str)

    client = await _http_client(loop)
    async with client.request(http_method,
                              url=url,
                              timeout=API_CALL_TIMEOUT, 
                              data=data_str,
                              headers=headers) as response:
        data = await response.json()
        if (response.status != 200) and (response.status != 204):
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {data}")
        return data

def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_forever()

def get_marketid_mapping() -> Dict[int, str]:
    global marketid_map
    if (marketid_map == None):
        loop = asyncio.new_event_loop()
        t = Thread(target=start_background_loop, args=(loop,), daemon=True)
        t.start()
        future = asyncio.run_coroutine_threadsafe(api_request("get", path_url="/markets",loop=loop) , loop)
        markets = future.result(constants.API_TIMEOUT_SEC)
        loop.stop()
        marketid_map = dict()
        for market in markets:
            marketid = market.get("id")
            if marketid not in marketid_map.keys():
                trad_pair = market.get("symbol")
                marketid_map[marketid]=trad_pair
    return marketid_map