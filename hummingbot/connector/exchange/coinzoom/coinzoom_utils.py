import aiohttp
import asyncio
import random
from dateutil.parser import parse as dateparse
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from .coinzoom_constants import Constants


CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = [0.2, 0.26]


class CoinzoomAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


# convert date string to timestamp
def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp() * 1e3)


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        return get_tracking_nonce()


def convert_from_exchange_trading_pair(ex_trading_pair: str) -> Optional[str]:
    # CoinZoom uses uppercase (BTC/USDT)
    return ex_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str, alternative: bool = False) -> str:
    # CoinZoom uses uppercase (BTCUSDT)
    if alternative:
        return hb_trading_pair.replace("-", "_").upper()
    else:
        return hb_trading_pair.replace("-", "/").upper()


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    symbols = trading_pair.split("-")
    base = symbols[0].upper()
    quote = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    return f"{Constants.HBOT_BROKER_ID}{side}{base_str}{quote_str}{get_tracking_nonce()}"


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
                if response.status not in [204]:
                    request_errors = True
                try:
                    parsed_response = str(await response.read())
                    if len(parsed_response) > 100:
                        parsed_response = f"{parsed_response[:100]} ... (truncated)"
                except Exception:
                    pass
            TempFailure = (parsed_response is None or
                           (response.status not in [200, 201, 204] and "error" not in parsed_response))
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
    headers = {"Content-Type": "application/json", "User-Agent": "hummingbot"}
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
            raise CoinzoomAPIError({"error": parsed_response, "status": http_status})
    return parsed_response


KEYS = {
    "coinzoom_api_key":
        ConfigVar(key="coinzoom_api_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("coinzoom"),
                  is_secure=True,
                  is_connect_key=True),
    "coinzoom_secret_key":
        ConfigVar(key="coinzoom_secret_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("coinzoom"),
                  is_secure=True,
                  is_connect_key=True),
    "coinzoom_username":
        ConfigVar(key="coinzoom_username",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} ZoomMe username >>> ",
                  required_if=using_exchange("coinzoom"),
                  is_secure=True,
                  is_connect_key=True),
}
