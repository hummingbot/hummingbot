from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True # TODO, undocumented, unclear how this affects operation
EXAMPLE_PAIR = "f43a62fdc3965df486de8a0d32fe800963589c41b38946602a0dc535.41474958_dda5fdb1002f7389b33e036b6afee82a8189becb6cba852e8b79b4fb.0014df1047454e53"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.3"),
    taker_percent_fee_decimal=Decimal("0.3"),
    buy_percent_fee_deducted_from_returns=False # TODO confirm correctness
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    return True


class BinanceConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="binance", const=True, client_data=None)
    binance_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    binance_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "binance"


KEYS = BinanceConfigMap.construct()

OTHER_DOMAINS = ["binance_us"]
OTHER_DOMAINS_PARAMETER = {"binance_us": "us"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_us": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_us": DEFAULT_FEES}


class BinanceUSConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="binance_us", const=True, client_data=None)
    binance_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance US API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    binance_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance US API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "binance_us"


OTHER_DOMAINS_KEYS = {"binance_us": BinanceUSConfigMap.construct()}
