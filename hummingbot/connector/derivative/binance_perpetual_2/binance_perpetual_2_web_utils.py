import aiohttp
import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from hummingbot.connector.derivative.binance_perpetual_2 import binance_perpetual_2_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BinancePerpetual2RESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json" if request.method == RESTMethod.POST else "application/x-www-form-urlencoded"
        )
        return request


def public_rest_url(path_url: str, domain: str = "binance_perpetual_2"):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "binance_perpetual_2" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = "binance_perpetual_2"):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "binance_perpetual_2" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(endpoint: str, domain: str = "binance_perpetual_2"):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "binance_perpetual_2" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url + endpoint


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DOMAIN,
        time_provider: Optional[callable] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
            BinancePerpetual2RESTPreProcessor(),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[BinancePerpetual2RESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
    )
    server_time = response["serverTime"]
    return server_time


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    if rule["contractType"] == "PERPETUAL" and rule["status"] == "TRADING":
        valid = True
    else:
        valid = False
    return valid


async def api_request(
    path: str,
    api_factory: Optional[WebAssistantsFactory] = None,
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DOMAIN,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    method: RESTMethod = RESTMethod.GET,
    is_auth_required: bool = False,
    return_err: bool = False,
    limit_id: Optional[str] = None,
    timeout: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
):
    throttler = throttler or create_throttler()

    api_factory = api_factory or build_api_factory(
        throttler=throttler,
        time_synchronizer=time_synchronizer,
        domain=domain,
    )

    rest_assistant = await api_factory.get_rest_assistant()

    if is_auth_required:
        url = private_rest_url(path, domain=domain)
    else:
        url = public_rest_url(path, domain=domain)

    limit_id = path if limit_id is None else limit_id
    if method == RESTMethod.GET:
        async with throttler.execute_task(limit_id):
            try:
                response = await rest_assistant.call(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                )
                return response
            except Exception as e:
                if return_err:
                    return e
                else:
                    raise e
    else:
        async with throttler.execute_task(limit_id):
            try:
                response = await rest_assistant.call(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                )
                return response
            except Exception as e:
                if return_err:
                    return e
                else:
                    raise e 