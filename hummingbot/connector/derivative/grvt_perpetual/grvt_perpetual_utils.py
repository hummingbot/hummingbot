from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# GRVT fee schedule: maker 0.02%, taker 0.05%
# https://grvt.io/docs/fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=True,
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "HBOT"


def hb_trading_pair_to_grvt_instrument(trading_pair: str) -> str:
    """
    Converts a hummingbot trading pair (e.g. ``BTC-USDT``) to a GRVT
    instrument identifier (e.g. ``BTC_USDT_Perp``).
    """
    base, quote = trading_pair.split("-")
    return f"{base}_{quote}_Perp"


def grvt_instrument_to_hb_trading_pair(instrument: str) -> str:
    """
    Converts a GRVT instrument (e.g. ``BTC_USDT_Perp``) to a hummingbot
    trading pair (e.g. ``BTC-USDT``).
    """
    # Strip the _Perp suffix
    without_suffix = instrument.replace("_Perp", "")
    parts = without_suffix.split("_")
    if len(parts) >= 2:
        base = parts[0]
        quote = parts[1]
        return f"{base}-{quote}"
    return instrument


def is_exchange_information_valid(instrument: dict) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its
    exchange information.

    :param instrument: the instrument info dict from the GRVT API
    :return: True if the instrument is active, False otherwise
    """
    # GRVT instruments have an 'is_active' field
    return instrument.get("is_active", True)


class GrvtPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual"
    grvt_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Ethereum private key (for order signing)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_sub_account_id: str = Field(
        default="0",
        json_schema_extra={
            "prompt": "Enter your GRVT sub-account ID (default: 0)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="grvt_perpetual")


KEYS = GrvtPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["grvt_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"grvt_perpetual_testnet": "grvt_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"grvt_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"grvt_perpetual_testnet": [0.02, 0.05]}


class GrvtPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual_testnet"
    grvt_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Ethereum private key (for order signing)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_testnet_sub_account_id: str = Field(
        default="0",
        json_schema_extra={
            "prompt": "Enter your GRVT sub-account ID (default: 0)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="grvt_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "grvt_perpetual_testnet": GrvtPerpetualTestnetConfigMap.model_construct()
}
