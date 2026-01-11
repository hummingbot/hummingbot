from typing import Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal="0.0002",
    taker_percent_fee_decimal="0.0005",
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"


class ArchitectPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="architect_perpetual", const=True, client_data=None)
    architect_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    architect_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = ArchitectPerpetualConfigMap.construct()


def is_exchange_information_valid(exchange_info: dict) -> bool:
    return exchange_info is not None and isinstance(exchange_info, dict) and "symbols" in exchange_info


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    if "/" in exchange_trading_pair:
        parts = exchange_trading_pair.split("/")
        base = parts[0].strip()
        quote = parts[1].strip() if len(parts) > 1 else "USD"
        if base.endswith(" Crypto"):
            base = base.replace(" Crypto", "")
        return f"{base}-{quote}"
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str, venue: Optional[str] = None) -> str:
    if "-" in hb_trading_pair:
        base, quote = hb_trading_pair.split("-")
        if venue == "COINBASE" or base in ["BTC", "ETH", "SOL", "AVAX"]:
            return f"{base} Crypto/{quote}"
        return f"{base}/{quote}"
    return hb_trading_pair


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    if "-" in trading_pair:
        parts = trading_pair.split("-")
        return parts[0], parts[1] if len(parts) > 1 else "USD"
    elif "/" in trading_pair:
        parts = trading_pair.split("/")
        base = parts[0].strip()
        if base.endswith(" Crypto"):
            base = base.replace(" Crypto", "")
        quote = parts[1].strip() if len(parts) > 1 else "USD"
        return base, quote
    return trading_pair, "USD"
