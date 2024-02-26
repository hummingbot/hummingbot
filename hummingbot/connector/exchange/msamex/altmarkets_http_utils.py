import aiohttp
import asyncio
import random

from typing import (
    Any,
    Callable,
    Dict,
    Optional,
)

import ujson

from hummingbot.connector.exchange.msamex.msamex_constants import Constants
from hummingbot.connector.exchange.msamex.msamex_utils import mSamexAPIError
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.logger import HummingbotLogger


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
                    parsed_response = await response.text('utf-8')
                    try:
                        parsed_response = ujson.loads(parsed_response)
                    except Exception:
                        if len(parsed_response) < 1:
                            parsed_response = None
                        elif len(parsed_response) > 100:
                            parsed_response = f"{parsed_response[:100]} ... (truncated)"
                except Exception:
                    pass
            TempFailure = (parsed_response is None or
                           (response.status not in [200, 201] and
                            "errors" not in parsed_response and
                            "error" not in parsed_response))
            if TempFailure:
                parsed_response = response.reason if parsed_response is None else parsed_response
                request_errors = True
    except Exception:
        request_errors = True
    return http_status, parsed_response, request_errors


async def api_call_with_retries(method,
                                endpoint,
                                auth_headers: Optional[Callable] = None,
                                extra_headers: Optional[Dict[str, str]] = None,
                                params: Optional[Dict[str, Any]] = None,
                                shared_client=None,
                                throttler: Optional[AsyncThrottler] = None,
                                limit_id: Optional[str] = None,
                                try_count: int = 0,
                                logger: HummingbotLogger = None,
                                disable_retries: bool = False) -> Dict[str, Any]:

    url = f"{Constants.REST_URL}/{endpoint}"
    headers = {"Content-Type": "application/json", "User-Agent": Constants.USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    if auth_headers:
        headers.update(auth_headers())
    http_client = shared_client or aiohttp.ClientSession()
    http_throttler = throttler or AsyncThrottler(Constants.RATE_LIMITS)
    _limit_id = limit_id or endpoint

    # Turn `params` into either GET params or POST body data
    qs_params: dict = params if method.upper() == "GET" else None
    req_params = ujson.dumps(params) if method.upper() == "POST" and params is not None else None

    async with http_throttler.execute_task(_limit_id):
        # Build request coro
        response_coro = http_client.request(method=method.upper(), url=url, headers=headers,
                                            params=qs_params, data=req_params, timeout=Constants.API_CALL_TIMEOUT)
        http_status, parsed_response, request_errors = await aiohttp_response_with_errors(response_coro)

    if shared_client is None:
        await http_client.close()

    if isinstance(parsed_response, dict) and ("errors" in parsed_response or "error" in parsed_response):
        parsed_response['errors'] = parsed_response.get('errors', parsed_response.get('error'))
        raise mSamexAPIError(parsed_response)

    if request_errors or parsed_response is None:
        if try_count < Constants.API_MAX_RETRIES and not disable_retries:
            try_count += 1
            time_sleep = retry_sleep_time(try_count)

            suppress_msgs = ['Forbidden']

            err_msg = (f"Error fetching data from {url}. HTTP status is {http_status}. "
                       f"Retrying in {time_sleep:.0f}s. {parsed_response or ''}")

            if (parsed_response is not None and parsed_response not in suppress_msgs) or try_count > 1:
                if logger:
                    logger.network(err_msg)
                else:
                    print(err_msg)
            elif logger:
                logger.debug(err_msg, exc_info=True)
            await asyncio.sleep(time_sleep)
            return await api_call_with_retries(method=method, endpoint=endpoint, extra_headers=extra_headers,
                                               params=params, shared_client=shared_client, throttler=throttler,
                                               limit_id=limit_id, try_count=try_count, logger=logger)
        else:
            raise mSamexAPIError({"errors": parsed_response, "status": http_status})
    return parsed_response
