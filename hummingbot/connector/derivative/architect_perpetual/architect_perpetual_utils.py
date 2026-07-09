from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(  # https://architect.co/legal/ax-pricing-policy section 5
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0025"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "EUR-USD"


class ArchitectPerpetualConfigMapBase(BaseConnectorConfigMap):
    use_auth_for_public_endpoints: bool = True  # used for MarketDataProvider.update_rates_task
    api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Architect Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Architect Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )


class ArchitectPerpetualConfigMap(ArchitectPerpetualConfigMapBase):
    connector: str = CONSTANTS.EXCHANGE_NAME
    model_config = ConfigDict(title=CONSTANTS.EXCHANGE_NAME)


KEYS = ArchitectPerpetualConfigMap.model_construct()

OTHER_DOMAINS = [CONSTANTS.SANDBOX_DOMAIN]
OTHER_DOMAINS_PARAMETER = {CONSTANTS.SANDBOX_DOMAIN: CONSTANTS.SANDBOX_DOMAIN}
OTHER_DOMAINS_EXAMPLE_PAIR = {CONSTANTS.SANDBOX_DOMAIN: EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {CONSTANTS.SANDBOX_DOMAIN: DEFAULT_FEES}


class ArchitectTestnetConfigMap(ArchitectPerpetualConfigMapBase):
    connector: str = CONSTANTS.SANDBOX_DOMAIN
    model_config = ConfigDict(title=CONSTANTS.SANDBOX_DOMAIN)


OTHER_DOMAINS_KEYS = {CONSTANTS.SANDBOX_DOMAIN: ArchitectTestnetConfigMap.model_construct()}
