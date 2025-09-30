import json
from turtle import pu
from typing import Optional

import hummingbot.connector.exchange.coinmate.coinmate_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import (
    WebAssistantsFactory
)


class CoinmateRESTPreProcessor(RESTPreProcessorBase):
    
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.POST and request.is_auth_required:
            if request.data:
                try:
                    data_dict = json.loads(request.data)
                    request.data = data_dict
                except (json.JSONDecodeError, TypeError):
                    pass
            
            headers = request.headers or {}
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            request.headers = headers
        
        return request


def public_rest_url(path_url: str, domain: str = None) -> str:
    return CONSTANTS.REST_URL + path_url

def private_rest_url(path_url: str, domain: str = None) -> str:
    return public_rest_url(path_url, domain)


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or AsyncThrottler(CONSTANTS.RATE_LIMITS)
    
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[CoinmateRESTPreProcessor()],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = None,
) -> float:
    try:
        throttler = throttler or AsyncThrottler(CONSTANTS.RATE_LIMITS)
        api_factory = build_api_factory_without_time_synchronizer_pre_processor(
            throttler
        )
        rest_assistant = await api_factory.get_rest_assistant()
        
        response = await rest_assistant.execute_request(
            url=public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
        )
        
        server_time = response.get("serverTime")
        if server_time is not None:
            return float(server_time)
            
    except Exception:
        pass
        
    import time
    return time.time() * 1000


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    if "_" in exchange_trading_pair:
        base, quote = exchange_trading_pair.split("_")
        return f"{base}-{quote}"
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    if "-" in hb_trading_pair:
        base, quote = hb_trading_pair.split("-")
        return f"{base}_{quote}"
    return hb_trading_pair


def get_exchange_base_quote_from_market_name(market_name: str) -> tuple:
    if "_" in market_name:
        return market_name.split("_")
    elif "-" in market_name:
        return market_name.split("-")
    else:
        for quote in CONSTANTS.SUPPORTED_QUOTE_CURRENCIES:
            if market_name.endswith(quote):
                base = market_name[:-len(quote)]
                return base, quote
        
        return market_name, ""
