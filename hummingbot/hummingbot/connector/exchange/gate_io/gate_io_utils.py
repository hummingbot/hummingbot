from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
)


class GateIOConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="gate_io", client_data=None)
    gate_io_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: f"Enter your {CONSTANTS.EXCHANGE_NAME} API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    gate_io_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: f"Enter your {CONSTANTS.EXCHANGE_NAME} secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "gate_io"


KEYS = GateIOConfigMap.construct()
