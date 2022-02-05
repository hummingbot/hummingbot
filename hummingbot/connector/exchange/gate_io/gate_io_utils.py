import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod, RESTResponse, EndpointRESTRequest
)
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = [0.2, 0.2]


@dataclass
class GateIORESTRequest(EndpointRESTRequest):
    @property
    def base_url(self) -> str:
        return CONSTANTS.REST_URL

    @property
    def auth_url(self) -> str:
        if self.endpoint is None:
            raise ValueError("No endpoint specified. Cannot build auth url.")
        auth_url = f"{CONSTANTS.REST_URL_AUTH}/{self.endpoint}"
        return auth_url


class GateIoAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload
        self.http_status = error_payload.get('status')
        if isinstance(error_payload, dict):
            self.error_message = error_payload.get('error', error_payload).get('message', error_payload)
            self.error_label = error_payload.get('error', error_payload).get('label', error_payload)
        else:
            self.error_message = error_payload
            self.error_label = error_payload


def build_gate_io_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    return api_factory


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = trading_pair.split('_')
        return m[0], m[1]
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(ex_trading_pair: str) -> Optional[str]:
    regex_match = split_trading_pair(ex_trading_pair)
    if regex_match is None:
        return None
    # Gate.io uses uppercase with underscore split (BTC_USDT)
    base_asset, quote_asset = split_trading_pair(ex_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Gate.io uses uppercase with underscore split (BTC_USDT)
    return hb_trading_pair.replace("-", "_").upper()


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    symbols = trading_pair.split("-")
    base = symbols[0].upper()
    quote = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    # Max length 30 chars including `t-`
    return f"{CONSTANTS.HBOT_ORDER_ID}-{side}-{base_str}{quote_str}{get_tracking_nonce()}"


def retry_sleep_time(try_count: int) -> float:
    random.seed()
    randSleep = 1 + float(random.randint(1, 10) / 100)
    return float(2 + float(randSleep * (1 + (try_count ** try_count))))


async def rest_response_with_errors(request_coroutine):
    http_status, parsed_response, request_errors = None, None, False
    try:
        response: RESTResponse = await request_coroutine
        http_status = response.status
        try:
            parsed_response = await response.json()
        except Exception:
            request_errors = True
            try:
                parsed_response = await response.text()
                if len(parsed_response) > 100:
                    parsed_response = f"{parsed_response[:100]} ... (truncated)"
            except Exception:
                pass
        TempFailure = (parsed_response is None or
                       (response.status not in [200, 201, 204] and "message" not in parsed_response))
        if TempFailure:
            parsed_response = (
                f"Failed with status code {response.status}" if parsed_response is None else parsed_response
            )
            request_errors = True
    except Exception:
        request_errors = True
    return http_status, parsed_response, request_errors


async def _sleep(delay):
    """
    Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
    """
    await asyncio.sleep(delay)


async def api_call_with_retries(request: GateIORESTRequest,
                                rest_assistant: RESTAssistant,
                                throttler: AsyncThrottler,
                                logger: logging.Logger,
                                gate_io_auth: Optional[GateIoAuth] = None,
                                try_count: int = 0) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}

    async with throttler.execute_task(limit_id=request.throttler_limit_id):
        if request.is_auth_required:
            if gate_io_auth is None:
                raise RuntimeError(
                    f"Authentication required for request, but no GateIoAuth object supplied."
                    f" Request: {request}."
                )
            auth_params = request.data if request.method == RESTMethod.POST else request.params
            request.data = auth_params
            headers: dict = gate_io_auth.get_headers(str(request.method), request.auth_url, auth_params)
        request.headers = headers
        response_coro = asyncio.wait_for(rest_assistant.call(request), CONSTANTS.API_CALL_TIMEOUT)
        http_status, parsed_response, request_errors = await rest_response_with_errors(response_coro)

    if request_errors or parsed_response is None:
        if try_count < CONSTANTS.API_MAX_RETRIES:
            try_count += 1
            time_sleep = retry_sleep_time(try_count)
            logger.info(
                f"Error fetching data from {request.url}. HTTP status is {http_status}."
                f" Retrying in {time_sleep:.0f}s."
            )
            await _sleep(time_sleep)
            return await api_call_with_retries(
                request, rest_assistant, throttler, logger, gate_io_auth, try_count
            )
        else:
            raise GateIoAPIError({"label": "HTTP_ERROR", "message": parsed_response, "status": http_status})

    if "message" in parsed_response:
        raise GateIoAPIError(parsed_response)

    return parsed_response


KEYS = {
    "gate_io_api_key":
        ConfigVar(key="gate_io_api_key",
                  prompt=f"Enter your {CONSTANTS.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("gate_io"),
                  is_secure=True,
                  is_connect_key=True),
    "gate_io_secret_key":
        ConfigVar(key="gate_io_secret_key",
                  prompt=f"Enter your {CONSTANTS.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("gate_io"),
                  is_secure=True,
                  is_connect_key=True),
}
