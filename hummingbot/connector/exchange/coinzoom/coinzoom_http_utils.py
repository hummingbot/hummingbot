import aiohttp
import asyncio
import random

from typing import (
    Any,
    Dict,
    Optional,
)

import ujson

from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants
from hummingbot.connector.exchange.coinzoom.coinzoom_utils import CoinzoomAPIError
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


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
            temp_failure = (parsed_response is None or
                            (response.status not in [200, 201, 204] and "error" not in parsed_response))
            if temp_failure:
                parsed_response = response.reason if parsed_response is None else parsed_response
                request_errors = True
    except Exception:
        request_errors = True
    return http_status, parsed_response, request_errors


async def api_call_with_retries(method,
                                endpoint,
                                extra_headers: Optional[Dict[str, str]] = None,
                                params: Optional[Dict[str, Any]] = None,
                                shared_client=None,
                                try_count: int = 0,
                                throttler: Optional[AsyncThrottler] = None,
                                limit_id: Optional[str] = None) -> Dict[str, Any]:

    url = f"{Constants.REST_URL}/{endpoint}"
    headers = {"Content-Type": "application/json", "User-Agent": "hummingbot"}
    if extra_headers:
        headers.update(extra_headers)
    http_client = shared_client or aiohttp.ClientSession()
    http_throttler = throttler or AsyncThrottler(Constants.RATE_LIMITS)
    limit_id = limit_id or endpoint

    # Turn `params` into either GET params or POST body data
    qs_params: dict = params if method.upper() == "GET" else None
    req_params = ujson.dumps(params) if method.upper() == "POST" and params is not None else None

    async with http_throttler.execute_task(limit_id):
        # Build request coro
        response_coro = http_client.request(method=method.upper(), url=url, headers=headers,
                                            params=qs_params, data=req_params, timeout=Constants.API_CALL_TIMEOUT)
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
