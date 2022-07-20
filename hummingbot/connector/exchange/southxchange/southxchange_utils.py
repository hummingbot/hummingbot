from datetime import datetime
from typing import Tuple, Optional, Dict
from dateutil import parser
import random
import string
from pydantic import Field, SecretStr
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.connector.exchange.southxchange.southxchange_web_utils import WebAssistantsFactory_SX
CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = [0.1, 0.1]


HBOT_BROKER_ID = "SX-HMBot"

_SX_throttler: AsyncThrottler


_last_tracking_nonce: int = 0


def get_tracking_nonce() -> int:
    global _last_tracking_nonce
    nonce = 1
    _last_tracking_nonce = nonce if nonce > _last_tracking_nonce else _last_tracking_nonce + 1
    return _last_tracking_nonce


def convert_string_to_datetime(fecha_str: str) -> datetime:
    try:
        fecha_str = str(f"{parser.parse(fecha_str).year}-{parser.parse(fecha_str).month}-{parser.parse(fecha_str).day}T{parser.parse(fecha_str).hour}:{parser.parse(fecha_str).minute}:{parser.parse(fecha_str).second}")
        return datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M:%S')
    except Exception as ex:
        _ = ex


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")


def get_exchange_trading_pair_from_currencies(listing_currecy: str, reference_currency: str) -> str:
    return listing_currecy + "/" + reference_currency


def time_to_num(time_str) -> int:
    hh, mm, ss = map(int, time_str.split(':'))
    return ss + 60 * (mm + 60 * hh)


def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def derive_order_id(cl_order_id: str, ts: int) -> str:
    """
    Server order generator based on user info and input.
    :param user_uid: user uid
    :param cl_order_id: user random digital and number id
    :param ts: order timestamp in milliseconds
    :return: order id of length 32
    """
    return (HBOT_BROKER_ID + format(ts, 'x')[-11:] + cl_order_id[-5:])[:32]


def convert_bookWebSocket_to_bookApi(t: any) -> Dict[str, list]:
    arrayBuy = []
    arraySell = []
    for item in t:
        if item.get("b") is True:
            buyOrder = {
                "Amount": item.get("a"),
                "Price": item.get("p")
            }
            arrayBuy.append(buyOrder)
        else:
            sellOrder = {
                "Amount": item.get("a"),
                "Price": item.get("p")
            }
            arraySell.append(sellOrder)
    result = {
        "BuyOrders": arrayBuy,
        "SellOrders": arraySell,
    }
    return result


def gen_exchange_order_id(client_order_id: str) -> Tuple[str, int]:
    """
    Generates the exchange order id based on user uid and client order id.
    :param user_uid: user uid,
    :param client_order_id: client order id used for local order tracking
    :return: order id of length 32
    """
    time = get_tracking_nonce()
    return [
        derive_order_id(
            client_order_id,
            time
        ),
        time
    ]


def gen_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{HBOT_BROKER_ID}-{side}-{trading_pair}-{get_tracking_nonce()}"


class SouthxchangeRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        # Generates generic headers required by AscendEx
        headers_generic = {}
        headers_generic["Accept"] = "application/json"
        headers_generic["Content-Type"] = "application/json"
        # Headers signature to identify user as an HB liquidity provider.
        request.headers = dict(list(headers_generic.items()) +
                               list(request.headers.items()))
        return request


def build_api_factory(throttler: AsyncThrottler, auth: Optional[AuthBase] = None) -> WebAssistantsFactory_SX:
    """
    Builds an API factory with custom REST preprocessors

    :param throttler: throttler instance to enforce rate limits
    :param auth: authentication class for private requests

    :return: API factory
    """
    api_factory = WebAssistantsFactory_SX(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[SouthxchangeRESTPreProcessor()])
    return api_factory


class SouthXchangeConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="southxchange", client_data=None)
    southxchange_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your SouthXchange API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    southxchange_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your SouthXchange secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "southxchange"


KEYS = SouthXchangeConfigMap.construct()
