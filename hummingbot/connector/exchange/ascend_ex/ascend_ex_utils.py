import random
import string
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


HBOT_BROKER_ID = "HMBot"


class AscendExRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        # Generates generic headers required by AscendEx
        headers_generic = {}
        headers_generic["Accept"] = "application/json"
        headers_generic["Content-Type"] = "application/json"
        # Headers signature to identify user as an HB liquidity provider.
        request.headers = dict(list(headers_generic.items()) +
                               list(request.headers.items()) +
                               list(get_hb_id_headers().items()))
        return request


def build_api_factory(throttler: AsyncThrottler, auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    """
    Builds an API factory with custom REST preprocessors

    :param throttler: throttler instance to enforce rate limits
    :param auth: authentication class for private requests

    :return: API factory
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[AscendExRESTPreProcessor()])
    return api_factory


def get_rest_url_private(account_id: int) -> str:
    """
    Builds a private REST URL

    :param account_id: account ID

    :return: a complete private REST URL
    """
    return f"https://ascendex.com/{account_id}/api/pro/v1/websocket-for-hummingbot-liq-mining"


def get_ws_url_private(account_id: int) -> str:
    """
    Builds a private websocket URL

    :param account_id: account ID

    :return: a complete private websocket URL
    """
    return f"wss://ascendex.com:443/{account_id}/api/pro/v1/websocket-for-hummingbot-liq-mining"


def get_hb_id_headers() -> Dict[str, Any]:
    """
    Headers signature to identify user as an HB liquidity provider.

    :return: a custom HB signature header
    """
    return {
        "request-source": "hummingbot-liq-mining",
    }


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return int(_time() * 1e3)


def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def derive_order_id(user_uid: str, cl_order_id: str, ts: int) -> str:
    """
    Server order generator based on user info and input.

    :param user_uid: user uid
    :param cl_order_id: user random digital and number id
    :param ts: order timestamp in milliseconds

    :return: order id of length 32
    """
    # NOTE: The derived_order_id function details how AscendEx server generates the exchange_order_id
    #       Currently, due to how the exchange constructs the exchange_order_id, there is a real possibility of
    #       duplicate order ids
    return (HBOT_BROKER_ID + format(ts, 'x')[-11:] + user_uid[-11:] + cl_order_id[-5:])[:32]


def gen_exchange_order_id(userUid: str, client_order_id: str, timestamp: Optional[int] = None) -> Tuple[str, int]:
    """
    Generates the exchange order id based on user uid and client order id.

    :param user_uid: user uid,
    :param client_order_id: client order id used for local order tracking

    :return: order id of length 32
    """
    time = timestamp or get_ms_timestamp()
    return [
        derive_order_id(
            userUid,
            client_order_id,
            time
        ),
        time
    ]


class AscendExConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ascend_ex", client_data=None)
    ascend_ex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your AscendEx API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ascend_ex_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your AscendEx secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "ascend_ex"


KEYS = AscendExConfigMap.construct()


def _time():
    """
    Private function created just to have a method that can be safely patched during unit tests and make tests
    independent from real time
    """
    return time.time()
