from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    return bool(exchange_info.get("symbol") or exchange_info.get("trading_pair") or exchange_info.get("market"))


class TwoFinanceConfigMap(BaseConnectorConfigMap):
    connector: str = "twofinance"
    twofinance_state_api_url: str = Field(
        default="http://127.0.0.1:8080/api/v1",
        json_schema_extra={
            "prompt": "Enter the 2Finance State API URL",
            "prompt_on_new": True,
            "is_connect_key": True,
        },
    )
    twofinance_matchengine_ws_url: str = Field(
        default="ws://127.0.0.1:10000",
        json_schema_extra={
            "prompt": "Enter the 2Finance MatchEngine WebSocket URL",
            "prompt_on_new": True,
            "is_connect_key": True,
        },
    )
    twofinance_matchengine_bearer_token: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the 2Finance MatchEngine bearer token",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    twofinance_engine_id: str = Field(
        default="engine-btc-usdt",
        json_schema_extra={"prompt": "Enter the 2Finance engine id", "prompt_on_new": True},
    )
    twofinance_wallet_id: int = Field(
        default=1,
        json_schema_extra={"prompt": "Enter the 2Finance wallet id", "prompt_on_new": True},
    )
    twofinance_account_id: str = Field(
        default="",
        json_schema_extra={"prompt": "Enter the optional 2Finance account id", "prompt_on_new": False},
    )
    model_config = ConfigDict(title="twofinance")


KEYS = TwoFinanceConfigMap.model_construct()

OTHER_DOMAINS = ["twofinance_testnet"]
OTHER_DOMAINS_PARAMETER = {"twofinance_testnet": "twofinance_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"twofinance_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"twofinance_testnet": [0, 0]}


class TwoFinanceTestnetConfigMap(TwoFinanceConfigMap):
    connector: str = "twofinance_testnet"
    model_config = ConfigDict(title="twofinance_testnet")


OTHER_DOMAINS_KEYS = {"twofinance_testnet": TwoFinanceTestnetConfigMap.model_construct()}
