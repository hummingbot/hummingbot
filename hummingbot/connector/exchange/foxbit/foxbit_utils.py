import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.foxbit import foxbit_constants as CONSTANTS
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-BRL"
_seq_nr: int = 0

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True
)


def get_client_order_id(is_buy: bool) -> str:
    """
    Creates a client order id for a new order
    :param is_buy: True if the order is a buy order, False if the order is a sell order
    :return: an identifier for the new order to be used in the client
    """
    newId = str(get_tracking_nonce())[4:]
    side = "00" if is_buy else "01"
    return f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{side}{newId}"


def get_ws_message_frame(endpoint: str,
                         msg_type: str = "0",
                         payload: str = "",
                         ) -> Dict[str, Any]:
    retValue = CONSTANTS.WS_MESSAGE_FRAME.copy()
    retValue["m"] = msg_type
    retValue["i"] = _get_next_message_frame_sequence_number()
    retValue["n"] = endpoint
    retValue["o"] = json.dumps(payload)
    return retValue


def _get_next_message_frame_sequence_number() -> int:
    """
    Returns next sequence number to be used into message frame for WS requests
    """
    global _seq_nr
    _seq_nr += 1
    return _seq_nr


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair. Dictionary with status and permissions
    :return: True if the trading pair is enabled, False otherwise

    Nowadays all available pairs are valid.
    It is here for future implamentation.
    """
    return True


def ws_data_to_dict(data: str) -> Dict[str, Any]:
    return eval(data.replace(":null", ":None").replace(":false", ":False").replace(":true", ":True"))


def datetime_val_or_now(string_value: str,
                        string_format: str = '%Y-%m-%dT%H:%M:%S.%fZ',
                        on_error_return_now: bool = True,
                        ) -> datetime:
    try:
        return datetime.strptime(string_value, string_format)
    except Exception:
        if on_error_return_now:
            return datetime.now()
        else:
            return None


def decimal_val_or_none(string_value: str,
                        on_error_return_none: bool = True,
                        ) -> Decimal:
    try:
        return Decimal(string_value)
    except Exception:
        if on_error_return_none:
            return None
        else:
            return Decimal('0')


def int_val_or_none(string_value: str,
                    on_error_return_none: bool = True,
                    ) -> int:
    try:
        return int(string_value)
    except Exception:
        if on_error_return_none:
            return None
        else:
            return int('0')


def get_order_state(state: str,
                    on_error_return_failed: bool = False,
                    ) -> OrderState:
    try:
        return CONSTANTS.ORDER_STATE[state]
    except Exception:
        if on_error_return_failed:
            return OrderState.FAILED
        else:
            return None


def get_base_quote_from_trading_pair(trading_pair: str):
    if len(trading_pair) == 0:
        return "", ""
    if trading_pair.find("-") == -1:
        return "", ""
    pair = trading_pair.split("-")
    return pair[0].upper(), pair[1].upper()


class FoxbitConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="foxbit", client_data=None)
    foxbit_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Foxbit API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    foxbit_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Foxbit API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    foxbit_user_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Foxbit User ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "foxbit"


KEYS = FoxbitConfigMap.construct()

OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}
