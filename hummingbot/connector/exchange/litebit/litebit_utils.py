from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-EUR"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("-0.01"),
    taker_percent_fee_decimal=Decimal("0.05"),
)


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status", None) == "active"


class LitebitConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="litebit", const=True, client_data=None)
    litebit_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your LiteBit API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    litebit_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your LiteBit API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "litebit"


KEYS = LitebitConfigMap.construct()


def convert_to_order_state(order_data: dict) -> OrderState:
    if order_data["status"] == "new":
        state = OrderState.PENDING_CREATE
    elif order_data["status"] == "open":
        if order_data["filled_status"] == "not_filled":
            state = OrderState.OPEN
        elif order_data["filled_status"] == "partially_filled":
            state = OrderState.PARTIALLY_FILLED
        else:
            raise ValueError(f"unexpected filled_status: {order_data['filled_status']}")
    elif order_data["status"] == "closed":
        if order_data["cancel_status"] is not None:
            if order_data["cancel_status"] == "cancelled_user":
                state = OrderState.CANCELED
            else:
                state = OrderState.FAILED
        else:
            state = OrderState.FILLED
    else:
        raise ValueError(f"unexpected status: {order_data['status']}")

    return state
