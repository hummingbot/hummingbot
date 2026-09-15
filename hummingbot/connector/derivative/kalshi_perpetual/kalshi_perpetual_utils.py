from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Base tier ($0 30-day volume): 5 bps maker, 12 bps taker, charged on notional in USD. Higher tiers are cheaper.
# https://docs.kalshi.com/margin-rest/fees/get-fee-tier-rates
# https://help.kalshi.com/en/articles/16071417-perps-fees-explained
DEFAULT_FEES = TradeFeeSchema(
    # Every fee is charged in USD, the collateral, whether the fill opens or closes a position.
    percent_fee_token="USD",
    maker_percent_fee_decimal=Decimal("0.0005"),
    taker_percent_fee_decimal=Decimal("0.0012"),
    # Paid from the USD collateral, so it adds to the cost instead of being deducted from what is received
    # (TradeFeeSchema requires this whenever percent_fee_token is set).
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = True

# Kalshi margin tickers look like KXBTCPERP and are quoted in USD.
EXAMPLE_PAIR = "BTC-USD"


class KalshiPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "kalshi_perpetual"
    kalshi_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Kalshi Perpetual API key ID",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    kalshi_perpetual_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Kalshi Perpetual RSA private key (PEM)",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


KEYS = KalshiPerpetualConfigMap.model_construct()
