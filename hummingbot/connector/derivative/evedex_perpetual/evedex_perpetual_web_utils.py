import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
    RESTResponse,
)
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant

from . import evedex_perpetual_constants as CONSTANTS

logger = logging.getLogger(__name__)


class EvedexPerpetualAPIError(Exception):
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class EvedexPerpetualRateLimitError(EvedexPerpetualAPIError):
    """Rate limit exceeded error."""
    pass


class EvedexPerpetualAuthError(EvedexPerpetualAPIError):
    """Authentication error."""
    pass


def get_rest_url(environment: str = "demo") -> str:
    return CONSTANTS.REST_URLS.get(environment, CONSTANTS.REST_URLS["demo"])


def get_ws_url(environment: str = "demo") -> str:
    return CONSTANTS.WS_URLS.get(environment, CONSTANTS.WS_URLS["demo"])


def build_api_throttler() -> AsyncThrottler:
    return AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)


async def api_request(
    rest_assistant: RESTAssistant,
    method: RESTMethod,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    throttler_limit_id: Optional[str] = None,
    timeout: float = CONSTANTS.HTTP_TIMEOUT,
) -> Dict[str, Any]:
    request = RESTRequest(
        method=method,
        url=url,
        params=params,
        data=data,
        headers=headers or {},
        is_auth_required=False,
        throttler_limit_id=throttler_limit_id,
    )
    
    try:
        response: RESTResponse = await rest_assistant.call(
            request, timeout=timeout
        )
        
        if response.status != 200:
            await handle_error_response(response)
        
        return await response.json()
        
    except aiohttp.ClientError as e:
        logger.error(f"HTTP client error: {e}")
        raise EvedexPerpetualAPIError(f"Network error: {e}")
    except asyncio.TimeoutError:
        logger.error(f"Request timeout after {timeout}s")
        raise EvedexPerpetualAPIError("Request timeout")


async def handle_error_response(response: RESTResponse) -> None:
    status = response.status
    
    try:
        error_data = await response.json()
        error_msg = error_data.get("message", "Unknown error")
        error_code = error_data.get("code")
    except Exception:
        error_msg = await response.text()
        error_code = None
    
    if status == 401:
        raise EvedexPerpetualAuthError(
            f"Authentication failed: {error_msg}",
            status_code=status,
            error_code=error_code,
        )
    
    if status == 429:
        raise EvedexPerpetualRateLimitError(
            f"Rate limit exceeded: {error_msg}",
            status_code=status,
            error_code=error_code,
        )
    
    if 400 <= status < 500:
        raise EvedexPerpetualAPIError(
            f"Client error ({status}): {error_msg}",
            status_code=status,
            error_code=error_code,
        )
    
    if status >= 500:
        raise EvedexPerpetualAPIError(
            f"Server error ({status}): {error_msg}",
            status_code=status,
            error_code=error_code,
        )
    
    raise EvedexPerpetualAPIError(
        f"Unknown error ({status}): {error_msg}",
        status_code=status,
        error_code=error_code,
    )


def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, EvedexPerpetualAuthError):
        return False
    
    if isinstance(error, EvedexPerpetualRateLimitError):
        return True  # Retry after cooldown
    
    if isinstance(error, EvedexPerpetualAPIError):
        if error.status_code and error.status_code >= 500:
            return True
    
    if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError)):
        return True  # Retry network errors
    
    return False


def parse_order_status(status: str) -> str:
    return CONSTANTS.ORDER_STATUS_MAP.get(status, "unknown")


def parse_order_side(side: str) -> str:
    return side.lower() if side else "unknown"


def parse_timestamp_ms(ts: Any) -> float:
    try:
        ts_float = float(ts)
        if ts_float > 1e10:
            return ts_float / 1000.0
        return ts_float
    except (TypeError, ValueError):
        return 0.0


def safe_ensure_future(coro, *args, **kwargs):
    return asyncio.ensure_future(coro, *args, **kwargs)
