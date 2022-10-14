from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Ftx fees: https://help.ftx.com/hc/en-us/articles/360024479432-Tarifas
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0007"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    is_futures_market = exchange_info.get("type", None) == "future"
    is_trading_enabled = exchange_info.get("enabled", False)
    market = exchange_info.get("name", False)
    if market:
        is_perp_market = market.split("-")[1] == "PERP"
    else:
        is_perp_market = False
    return is_futures_market and is_trading_enabled and is_perp_market


def get_next_funding_timestamp(current_timestamp: float) -> float:
    # On Ftx Perpetuals, funding occurs every 1 hour.
    # Reference: https://help.ftx.com/hc/en-us/articles/360027946571-Funding
    int_ts = int(current_timestamp)
    one_hour = 1 * 60 * 60
    mod = int_ts % one_hour
    return float(int_ts - mod + one_hour)


class FtxPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ftx_perpetual", client_data=None)
    ftx_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ftx Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ftx_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ftx Perpetual secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "ftx_perpetual"


KEYS = FtxPerpetualConfigMap.construct()
