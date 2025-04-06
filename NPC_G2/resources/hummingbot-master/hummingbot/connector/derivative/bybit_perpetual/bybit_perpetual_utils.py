from decimal import Decimal
from typing import Any, Dict, List, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Bybit fees: https://help.bybit.com/hc/en-us/articles/360039261154
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0006"),
    taker_percent_fee_decimal=Decimal("0.0001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    contract_type = exchange_info.get("contractType")
    status = exchange_info.get("status")
    valid = (status is not None and contract_type is not None
             and status in ["Trading", "Settling"] and contract_type in ["LinearPerpetual", "InversePerpetual"])
    return valid


def get_linear_non_linear_split(trading_pairs: List[str]) -> Tuple[List[str], List[str]]:
    linear_trading_pairs = []
    non_linear_trading_pairs = []
    for trading_pair in trading_pairs:
        if is_linear_perpetual(trading_pair):
            linear_trading_pairs.append(trading_pair)
        else:
            non_linear_trading_pairs.append(trading_pair)
    return linear_trading_pairs, non_linear_trading_pairs


def is_linear_perpetual(trading_pair: str) -> bool:
    """
    Returns True if trading_pair is in USDT(Linear) Perpetual
    """
    _, quote_asset = split_hb_trading_pair(trading_pair)
    return quote_asset == "USDT"


def get_next_funding_timestamp(current_timestamp: float) -> float:
    # On ByBit Perpetuals, funding occurs every 8 hours at 00:00UTC, 08:00UTC and 16:00UTC.
    # Reference: https://help.bybit.com/hc/en-us/articles/360039261134-Funding-fee-calculation
    int_ts = int(current_timestamp)
    eight_hours = 8 * 60 * 60
    mod = int_ts % eight_hours
    return float(int_ts - mod + eight_hours)


class BybitPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bybit_perpetual", client_data=None)
    bybit_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bybit Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bybit_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bybit Perpetual secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bybit_perpetual"


KEYS = BybitPerpetualConfigMap.construct()

OTHER_DOMAINS = ["bybit_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"bybit_perpetual_testnet": "bybit_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bybit_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {
    "bybit_perpetual_testnet": TradeFeeSchema(
        maker_percent_fee_decimal=Decimal("-0.00025"),
        taker_percent_fee_decimal=Decimal("0.00075"),
    )
}


class BybitPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bybit_perpetual_testnet", client_data=None)
    bybit_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bybit Perpetual Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bybit_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bybit Perpetual Testnet secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bybit_perpetual_testnet"


OTHER_DOMAINS_KEYS = {
    "bybit_perpetual_testnet": BybitPerpetualTestnetConfigMap.construct()
}
