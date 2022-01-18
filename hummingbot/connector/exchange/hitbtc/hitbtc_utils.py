import aiohttp
import asyncio
import random
import re
from dateutil.parser import parse as dateparse
from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from .hitbtc_constants import Constants


TRADING_PAIR_SPLITTER = re.compile(Constants.TRADING_PAIR_SPLITTER)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = [0.1, 0.25]


class HitbtcAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


# convert date string to timestamp
def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp())


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        return get_tracking_nonce()


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        if trading_pair == 'USDTUSD':
            return 'USD', 'TUSD'
        elif trading_pair == 'USDTGUSD':
            return 'USD', 'GUSD'
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def translate_asset(asset_name: str) -> str:
    asset_replacements = [
        ("USD", "USDT"),
    ]
    for asset_replacement in asset_replacements:
        for inv in [0, 1]:
            if asset_name == asset_replacement[inv]:
                return asset_replacement[(0 if inv else 1)]
    return asset_name


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    symbols = trading_pair.split("-")
    base = symbols[0].upper()
    quote = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    return f"{Constants.HBOT_BROKER_ID}-{side}-{base_str}{quote_str}-{get_tracking_nonce()}"


def retry_sleep_time(try_count: int) -> float:
    random.seed()
    randSleep = 1 + float(random.randint(1, 10) / 100)
    return float(2 + float(randSleep * (1 + (try_count ** try_count))))


async def aiohttp_response_with_errors(request_coroutine):
    http_status, parsed_response, request_errors = None, None, False
    try:
        async with request_coroutine as response:
            http_status = response.status
            try:
                parsed_response = await response.json()
            except Exception:
                request_errors = True
                try:
                    parsed_response = str(await response.read())
                    if len(parsed_response) > 100:
                        parsed_response = f"{parsed_response[:100]} ... (truncated)"
                except Exception:
                    pass
            TempFailure = (parsed_response is None or
                           (response.status not in [200, 201] and "error" not in parsed_response))
            if TempFailure:
                parsed_response = response.reason if parsed_response is None else parsed_response
                request_errors = True
    except Exception:
        request_errors = True
    return http_status, parsed_response, request_errors


async def api_call_with_retries(method,
                                endpoint,
                                params: Optional[Dict[str, Any]] = None,
                                shared_client=None,
                                try_count: int = 0) -> Dict[str, Any]:
    url = f"{Constants.REST_URL}/{endpoint}"
    headers = {"Content-Type": "application/json"}
    http_client = shared_client if shared_client is not None else aiohttp.ClientSession()
    # Build request coro
    response_coro = http_client.request(method=method.upper(), url=url, headers=headers,
                                        params=params, timeout=Constants.API_CALL_TIMEOUT)
    http_status, parsed_response, request_errors = await aiohttp_response_with_errors(response_coro)
    if shared_client is None:
        await http_client.close()
    if request_errors or parsed_response is None:
        if try_count < Constants.API_MAX_RETRIES:
            try_count += 1
            time_sleep = retry_sleep_time(try_count)
            print(f"Error fetching data from {url}. HTTP status is {http_status}. "
                  f"Retrying in {time_sleep:.0f}s.")
            await asyncio.sleep(time_sleep)
            return await api_call_with_retries(method=method, endpoint=endpoint, params=params,
                                               shared_client=shared_client, try_count=try_count)
        else:
            raise HitbtcAPIError({"error": parsed_response, "status": http_status})
    return parsed_response


KEYS = {
    "hitbtc_api_key":
        ConfigVar(key="hitbtc_api_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("hitbtc"),
                  is_secure=True,
                  is_connect_key=True),
    "hitbtc_secret_key":
        ConfigVar(key="hitbtc_secret_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("hitbtc"),
                  is_secure=True,
                  is_connect_key=True),
}
