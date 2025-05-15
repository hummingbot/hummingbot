from dataclasses import dataclass
from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as constants
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest

CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.004"),
    taker_percent_fee_decimal=Decimal("0.006"),
    buy_percent_fee_deducted_from_returns=False
)


@dataclass
class CoinbaseAdvancedTradeRESTRequest(EndpointRESTRequest):
    def __post_init__(self):
        super().__post_init__()
        self._ensure_endpoint_for_auth()

    @property
    def base_url(self) -> str:
        return constants.REST_URL

    def _ensure_endpoint_for_auth(self):
        if self.is_auth_required and self.endpoint is None:
            raise ValueError("The endpoint must be specified if authentication is required.")


class CoinbaseAdvancedTradeConfigMap(BaseConnectorConfigMap):
    connector: str = "coinbase_advanced_trade"
    use_auth_for_public_endpoints: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Would you like to use authentication for public endpoints? (Yes/No) (only affects rate limiting)",
            "prompt_on_new": True,
            "is_connect_key": True
        }
    )
    coinbase_advanced_trade_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Coinbase Advanced Trade API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    coinbase_advanced_trade_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Coinbase Advanced Trade API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="coinbase_advanced_trade")


KEYS = CoinbaseAdvancedTradeConfigMap.model_construct()
