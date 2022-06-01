from decimal import Decimal
from enum import Enum
from typing import Any, Dict

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
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

KEYS = {
    "latoken_api_key":
        ConfigVar(key="latoken_api_key",
                  prompt="Enter your Latoken API key >>> ",
                  required_if=using_exchange("latoken"),
                  is_secure=True,
                  is_connect_key=True),
    "latoken_api_secret":
        ConfigVar(key="latoken_api_secret",
                  prompt="Enter your Latoken API secret >>> ",
                  required_if=using_exchange("latoken"),
                  is_secure=True,
                  is_connect_key=True),
}
