from decimal import Decimal
from typing import Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


CENTRALIZED = True
EXAMPLE_PAIR = "ES-USD"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
)


def is_exchange_information_valid(exchange_info: dict) -> bool:
    return exchange_info is not None and len(exchange_info) > 0


class ArchitectPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="architect_perpetual", const=True, client_data=None)
    architect_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    architect_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    architect_perpetual_paper_trading: bool = Field(
        default=False,
        client_data=ClientFieldData(
            prompt=lambda cm: "Use paper trading mode? (True/False)",
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "architect_perpetual"


KEYS = ArchitectPerpetualConfigMap.construct()
