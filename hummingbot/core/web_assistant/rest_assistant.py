import json
import math
import time
from asyncio import wait_for
from copy import deepcopy
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Mapping, Optional, Union

from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase

# Headers exchanges use to say how long to wait before sending again. Retry-After is the
# standard one (RFC 9110). The others are common but less strictly defined, so they are
# checked after it.
_RETRY_AFTER_HEADERS = ("Retry-After", "RateLimit-Reset", "X-RateLimit-Reset")

# A value this large is a timestamp, not a number of seconds to wait. Some exchanges send
# the time the limit resets instead of how long to wait, even in headers meant for a delay.
_EPOCH_THRESHOLD_SECONDS = 1_000_000_000.0

# HTTP statuses that mean we are sending too many requests.
RATE_LIMITED_STATUSES = (418, 429)
# Binance and some others send this once an IP has been banned for ignoring 429s.
BANNED_STATUS = 418


def retry_after_from_headers(headers: Mapping[str, Any], now: Optional[float] = None) -> Optional[float]:
    """Seconds to wait before sending again, read from a 429 response's headers.

    Returns None if there is no such header or its value can't be read. The throttler then
    waits for the limit's own time window instead.
    """
    # When the exchange gives a time rather than a delay, measure it against the exchange's
    # own clock (the response's Date header) if we have it, so a difference between our
    # clock and theirs doesn't change how long we wait.
    server_now = _http_date_to_timestamp(headers.get("Date"))
    now = server_now if server_now is not None else (time.time() if now is None else now)
    for name in _RETRY_AFTER_HEADERS:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            # Retry-After can also be a date, like "Wed, 21 Oct 2015 07:28:00 GMT".
            retry_at = _http_date_to_timestamp(raw)
            if retry_at is None:
                continue
            return retry_at - now
        if not math.isfinite(value):
            # "inf" and "nan" parse as numbers but aren't a real wait.
            continue
        if value > _EPOCH_THRESHOLD_SECONDS:
            # A timestamp. If it's even larger, it's in milliseconds.
            if value > _EPOCH_THRESHOLD_SECONDS * 1000:
                value /= 1000.0
            return value - now
        return value
    return None


def _http_date_to_timestamp(raw: Any) -> Optional[float]:
    """Unix time for an HTTP date header value, or None if it isn't one."""
    if not isinstance(raw, str):
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:
        # Older Python versions return None instead of raising for an empty or bad value.
        return None
    if parsed.tzinfo is None:
        # HTTP dates are always in GMT.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


class RESTAssistant:
    """A helper class to contain all REST-related logic.

    The class can be injected with additional functionality by passing a list of objects inheriting from
    the `RESTPreProcessorBase` and `RESTPostProcessorBase` classes. The pre-processors are applied to a request
    before it is sent out, while the post-processors are applied to a response before it is returned to the caller.
    """

    def __init__(
        self,
        connection: RESTConnection,
        throttler: AsyncThrottlerBase,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connection = connection
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._auth = auth
        self._throttler = throttler

    async def execute_request(
        self,
        url: str,
        throttler_limit_id: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        method: RESTMethod = RESTMethod.GET,
        is_auth_required: bool = False,
        return_err: bool = False,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Dict[str, Any]]:
        response = await self.execute_request_and_get_response(
            url=url,
            throttler_limit_id=throttler_limit_id,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            return_err=return_err,
            timeout=timeout,
            headers=headers,
        )
        response_json = await response.json()
        return response_json

    async def execute_request_and_get_response(
            self,
            url: str,
            throttler_limit_id: str,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            method: RESTMethod = RESTMethod.GET,
            is_auth_required: bool = False,
            return_err: bool = False,
            timeout: Optional[float] = None,
            headers: Optional[Dict[str, Any]] = None,
    ) -> RESTResponse:

        headers = headers or {}

        local_headers = {
            "Content-Type": ("application/json" if method != RESTMethod.GET else "application/x-www-form-urlencoded")}

        local_headers.update(headers)

        data = json.dumps(data) if data is not None else data

        request = RESTRequest(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=local_headers,
            is_auth_required=is_auth_required,
            throttler_limit_id=throttler_limit_id
        )

        async with self._throttler.execute_task(limit_id=throttler_limit_id):
            response = await self.call(request=request, timeout=timeout)

            if 400 <= response.status:
                # 429 means too many requests. Binance and some others send 418 once an IP has been
                # banned for ignoring 429s, also with a Retry-After header.
                if response.status in RATE_LIMITED_STATUSES:
                    await self._throttler.pause_after_too_many_requests(
                        limit_id=throttler_limit_id,
                        retry_after=retry_after_from_headers(response.headers or {}),
                        banned=response.status == BANNED_STATUS,
                    )
                if not return_err:
                    error_response = await response.text()
                    error_text = "N/A" if "<html" in error_response else error_response
                    raise IOError(f"Error executing request {method.name} {url}. HTTP status is {response.status}. "
                                  f"Error: {error_text}")
            return response

    async def call(self, request: RESTRequest, timeout: Optional[float] = None) -> RESTResponse:
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        request = await self._authenticate(request)
        resp = await wait_for(self._connection.call(request), timeout)
        resp = await self._post_process_response(resp)
        return resp

    async def _pre_process_request(self, request: RESTRequest) -> RESTRequest:
        for pre_processor in self._rest_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _authenticate(self, request: RESTRequest):
        if self._auth is not None and request.is_auth_required:
            request = await self._auth.rest_authenticate(request)
        return request

    async def _post_process_response(self, response: RESTResponse) -> RESTResponse:
        for post_processor in self._rest_post_processors:
            response = await post_processor.post_process(response)
        return response
