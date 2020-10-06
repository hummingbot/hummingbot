import logging
from typing import Dict, Any, Optional, Tuple, List
import hummingbot.connector.exchange.eterbase.eterbase_constants as constants
from hummingbot.connector.exchange.eterbase.eterbase_auth import EterbaseAuth

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
import aiohttp
import asyncio
import json
from threading import Thread

_eu_logger = logging.getLogger(__name__)

shared_client = None

marketid_map = None

API_CALL_TIMEOUT = 10.0

CENTRALIZED = True

EXAMPLE_PAIR = "EUR-ETH"

DEFAULT_FEES = [0.35, 0.35]


async def _http_client(loop: Optional = None) -> aiohttp.ClientSession:
    """
    :returns: Shared client session instance
    """

    # calling API from different thread
    if loop is not None:
        return aiohttp.ClientSession(loop = loop)

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
    data_str = None

    if data is not None:
        data_str = json.dumps(data)

    _eu_logger.debug(f"Request: url: {url}")
    _eu_logger.debug(f"Request: data: {data_str}")

    headers = {}

    if auth is not None:
        headers = auth.get_headers(http_method, url, data_str)

    if data is not None:
        headers['Content-Type'] = "application/json"

    client = await _http_client(loop)
    async with client.request(http_method,
                              url=url,
                              timeout=API_CALL_TIMEOUT,
                              data=data_str,
                              headers=headers) as response:
        data = None
        data = await response.text()
        _eu_logger.debug(f"Response text data: '{data}'."[:400])
        if len(data) > 0:
            try:
                data = json.loads(data)
            except ValueError:
                _eu_logger.info(f"Response is not a json text: '{data}'."[:400])
        if (response.status != 200) and (response.status != 204):
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {data}", response.status)
        return data


def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_forever()


def get_marketid_mapping() -> Dict[int, str]:
    global marketid_map
    if (marketid_map is None):
        loop = asyncio.new_event_loop()
        t = Thread(target=start_background_loop, args=(loop, ), daemon=True)
        t.start()
        future = asyncio.run_coroutine_threadsafe(api_request("get", path_url="/markets", loop=loop), loop)
        markets = future.result(constants.API_TIMEOUT_SEC)
        loop.stop()

        marketid_map = dict()
        for market in markets:
            marketid = market.get("id")
            if marketid not in marketid_map.keys():
                trad_pair = market.get("symbol")
                marketid_map[marketid] = trad_pair
    return marketid_map


trading_pairs_split = None


def prepare_trading_pairs_split(markets: List):
    global trading_pairs_split
    if trading_pairs_split is None:
        trading_pairs_split = dict()
    for market in markets:
        trad_pair = market.get("symbol")
        if trad_pair not in trading_pairs_split:
            base = market.get("base")
            quote = market.get("quote")
            trading_pairs_split[trad_pair] = {"base": base, "quote": quote}


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    global trading_pairs_split
    if (trading_pairs_split is None):
        loop = asyncio.new_event_loop()
        t = Thread(target=start_background_loop, args=(loop, ), daemon=True)
        t.start()
        future = asyncio.run_coroutine_threadsafe(api_request("get", path_url="/markets", loop=loop), loop)
        markets = future.result(constants.API_TIMEOUT_SEC)
        loop.stop()
        prepare_trading_pairs_split(markets)
    try:
        market = trading_pairs_split[trading_pair]
        base_asset = market['base']
        quote_asset = market['quote']
        return base_asset, quote_asset
    except Exception:
        raise ValueError(f"Error parsing trading_pair {trading_pair}", exc_info=True)


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def convert_from_exchange_trading_pair(trading_pair: str) -> str:
    base, quote = split_trading_pair(trading_pair)
    return f"{base}-{quote}"


KEYS = {
    "eterbase_api_key":
        ConfigVar(key="eterbase_api_key",
                  prompt="Enter your Eterbase API key >>> ",
                  required_if=using_exchange("eterbase"),
                  is_secure=True,
                  is_connect_key=True),
    "eterbase_secret_key":
        ConfigVar(key="eterbase_secret_key",
                  prompt="Enter your Eterbase secret key >>> ",
                  required_if=using_exchange("eterbase"),
                  is_secure=True,
                  is_connect_key=True),
    "eterbase_account":
        ConfigVar(key="eterbase_account",
                  prompt="Enter your Eterbase account >>> ",
                  required_if=using_exchange("eterbase"),
                  is_secure=True,
                  is_connect_key=True),
}
