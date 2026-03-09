from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Bluefin is a decentralized exchange
CENTRALIZED = False

# Example trading pair
EXAMPLE_PAIR = "BTC-USD"

# Default fee structure
# Based on Bluefin's standard fee schedule
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),  # 0.01%
    taker_percent_fee_decimal=Decimal("0.0005"),  # 0.05%
    buy_percent_fee_deducted_from_returns=True
)


class BluefinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "bluefin_perpetual"

    bluefin_perpetual_wallet_mnemonic: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bluefin wallet mnemonic (24 words)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    bluefin_perpetual_network: Literal["MAINNET", "STAGING"] = Field(
        default="MAINNET",
        json_schema_extra={
            "prompt": "Select network (MAINNET/STAGING)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    model_config = ConfigDict(title="bluefin_perpetual")


KEYS = BluefinPerpetualConfigMap.model_construct()
