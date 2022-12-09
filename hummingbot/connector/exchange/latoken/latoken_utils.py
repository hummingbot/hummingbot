from decimal import Decimal
from enum import Enum
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


class LatokenCommissionType(Enum):
    PERCENT = 1
    ABSOLUTE = 2


class LatokenTakeType(Enum):
    PROPORTION = 1
    ABSOLUTE = 2


class LatokenFeeSchema:
    def __init__(self, fee_schema: Dict[str, Any]):
        if fee_schema is None:
            return
        self.maker_fee = Decimal(fee_schema["makerFee"])
        self.taker_fee = Decimal(fee_schema["takerFee"])
        self.type = fee_type[fee_schema["type"]]
        self.take = fee_take[fee_schema["take"]]


CENTRALIZED = True
EXAMPLE_PAIR = "LA-USDT"
DEFAULT_FEES = TradeFeeSchema(maker_percent_fee_decimal=Decimal("0.001"), taker_percent_fee_decimal=Decimal("0.001"))
fee_type = {"FEE_SCHEME_TYPE_PERCENT_QUOTE": LatokenCommissionType.PERCENT}
fee_take = {"FEE_SCHEME_TAKE_PROPORTION": LatokenTakeType.PROPORTION}


class LatokenConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="latoken", const=True, client_data=None)
    latoken_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Latoken API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    latoken_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Latoken API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "latoken"


KEYS = LatokenConfigMap.construct()
