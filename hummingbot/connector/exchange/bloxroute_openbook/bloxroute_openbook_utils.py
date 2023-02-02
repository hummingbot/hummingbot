import math
from decimal import Decimal
from typing import Any, Dict

import bxsolana_trader_proto.api as api
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

EXAMPLE_PAIR = "SOL-USDC"

DEFAULT_FEES = TradeFeeSchema(
    buy_percent_fee_deducted_from_returns=True,
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """

    ##TODO: this needs some logic to make sure that the exchange info is valid and not just return true
    return True


class BloxRouteConnectorMap(BaseConnectorConfigMap):
    connector: str = Field(default="bloxroute_openbook", client_data=None)
    bloxroute_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter bloxroute Labs authorization header",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    solana_wallet_public_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your solana wallet public key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    solana_wallet_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your solana wallet secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    open_orders_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter bloxroute Labs open orders address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "bloxroute_openbook"


KEYS = BloxRouteConnectorMap.construct()


# def TradeTypeToSide(type: TradeType) -> api.Side:
#     if type.value == type.BUY:
#         return api.Side.S_BID
#     elif type.value == type.SELL:
#         return api.Side.S_ASK
#     else:
#         return api.Side.S_UNKNOWN
#
#
# def OrderTypeToBlxrOrderType(orderType: OrderType) -> api.OrderType:
#     if orderType.value == orderType.MARKET:
#         return api.OrderType.OT_MARKET
#     elif orderType.value == orderType.LIMIT:
#         return api.OrderType.OT_LIMIT
#     else:
#         raise Exception(f"unknown order type ${orderType.value}")  # TODO need unknown value
