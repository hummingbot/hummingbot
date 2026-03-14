from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Architect fees vary by venue/product; these are typical Binance perp fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),   # 0.02% maker
    taker_percent_fee_decimal=Decimal("0.0005"),   # 0.05% taker
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"


def order_status_to_hummingbot(status: str) -> OrderState:
    return CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN)


class ArchitectPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="architect_perpetual", const=True, client_data=None)

    architect_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    architect_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    architect_execution_venue: str = Field(
        default=CONSTANTS.DEFAULT_EXECUTION_VENUE,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter execution venue (e.g. BINANCE, CME)",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "architect_perpetual"


KEYS = ArchitectPerpetualConfigMap.construct()
OTHER_DOMAINS = [CONSTANTS.PAPER_DOMAIN]
OTHER_DOMAINS_PARAMETER = {CONSTANTS.PAPER_DOMAIN: CONSTANTS.PAPER_DOMAIN}
OTHER_DOMAINS_EXAMPLE_PAIR = {CONSTANTS.PAPER_DOMAIN: "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {CONSTANTS.PAPER_DOMAIN: DEFAULT_FEES}


class ArchitectPerpetualPaperConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default=CONSTANTS.PAPER_DOMAIN, const=True, client_data=None)

    architect_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API key (paper trading)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    architect_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect API secret (paper trading)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    architect_execution_venue: str = Field(
        default=CONSTANTS.DEFAULT_EXECUTION_VENUE,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter execution venue (e.g. BINANCE)",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = CONSTANTS.PAPER_DOMAIN


OTHER_DOMAINS_KEYS = {CONSTANTS.PAPER_DOMAIN: ArchitectPerpetualPaperConfigMap.construct()}
