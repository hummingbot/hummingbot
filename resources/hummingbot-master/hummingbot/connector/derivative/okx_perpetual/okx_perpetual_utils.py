from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# https://www.okx.com/es-la/fees/
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return (exchange_info.get("instType") == "SWAP"
            and exchange_info.get("ctType") == "linear"
            and exchange_info.get("state") == "live")


def is_linear_perpetual(trading_pair: str) -> bool:
    """
    Returns True if trading_pair is in USDT(Linear) Perpetual
    """
    _, quote_asset = split_hb_trading_pair(trading_pair)
    return quote_asset in ["USDT", "USDC"]


def get_next_funding_timestamp(current_timestamp: float) -> float:
    # On Okx Perpetuals, funding occurs every 8 hours at 00:00UTC, 08:00UTC and 16:00UTC.
    # Reference: https://help.okx.com/hc/en-us/articles/360039261134-Funding-fee-calculation
    int_ts = int(current_timestamp)
    eight_hours = 8 * 60 * 60
    mod = int_ts % eight_hours
    return float(int_ts - mod + eight_hours)


class OkxPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="okx_perpetual", client_data=None)
    okx_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Okx Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    okx_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Okx Perpetual secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    okx_perpetual_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Okx Perpetual passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "okx_perpetual"


KEYS = OkxPerpetualConfigMap.construct()
