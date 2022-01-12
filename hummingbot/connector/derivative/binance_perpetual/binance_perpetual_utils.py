import os
import socket
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USDT"


DEFAULT_FEES = [0.02, 0.04]


BROKER_ID = "x-3QreWesy"


class BinancePerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json" if request.method == RESTMethod.POST else "application/x-www-form-urlencoded"
        )
        return request


def get_client_order_id(order_side: str, trading_pair: object):
    nonce = get_tracking_nonce()
    symbols: str = trading_pair.split("-")
    base: str = symbols[0].upper()
    quote: str = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]
    return f"{BROKER_ID}-{order_side.upper()[0]}{base_str}{quote_str}{client_instance_id}{nonce}"


def rest_url(path_url: str, domain: str = "binance_perpetual", api_version: str = CONSTANTS.API_VERSION):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "binance_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + api_version + path_url


def wss_url(endpoint: str, domain: str = "binance_perpetual"):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "binance_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url + endpoint


def build_api_factory(auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(auth=auth, rest_pre_processors=[BinancePerpetualRESTPreProcessor()])
    return api_factory


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status", None) == "TRADING"


KEYS = {
    "binance_perpetual_api_key": ConfigVar(
        key="binance_perpetual_api_key",
        prompt="Enter your Binance Perpetual API key >>> ",
        required_if=using_exchange("binance_perpetual"),
        is_secure=True,
        is_connect_key=True,
    ),
    "binance_perpetual_api_secret": ConfigVar(
        key="binance_perpetual_api_secret",
        prompt="Enter your Binance Perpetual API secret >>> ",
        required_if=using_exchange("binance_perpetual"),
        is_secure=True,
        is_connect_key=True,
    ),
}

OTHER_DOMAINS = ["binance_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"binance_perpetual_testnet": "binance_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_perpetual_testnet": [0.02, 0.04]}
OTHER_DOMAINS_KEYS = {
    "binance_perpetual_testnet": {
        # add keys for testnet
        "binance_perpetual_testnet_api_key": ConfigVar(
            key="binance_perpetual_testnet_api_key",
            prompt="Enter your Binance Perpetual testnet API key >>> ",
            required_if=using_exchange("binance_perpetual_testnet"),
            is_secure=True,
            is_connect_key=True,
        ),
        "binance_perpetual_testnet_api_secret": ConfigVar(
            key="binance_perpetual_testnet_api_secret",
            prompt="Enter your Binance Perpetual testnet API secret >>> ",
            required_if=using_exchange("binance_perpetual_testnet"),
            is_secure=True,
            is_connect_key=True,
        ),
    }
}
