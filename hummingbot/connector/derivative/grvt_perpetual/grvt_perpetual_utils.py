from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_web_utils as web_utils
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # 0.02% maker
    taker_percent_fee_decimal=Decimal("0.0005"),  # 0.05% taker
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

# Time-in-force mapping from Hummingbot to GRVT integer values
TIME_IN_FORCE_MAP = {
    "GTC": 1,   # GOOD_TILL_TIME
    "IOC": 3,   # IMMEDIATE_OR_CANCEL
    "FOK": 4,   # FILL_OR_KILL
    "GTD": 1,   # treat same as GTC
}


def is_exchange_information_valid(instrument_info: Dict[str, Any]) -> bool:
    """Return True if instrument is active perpetual."""
    return (
        instrument_info.get("kind") == "PERPETUAL"
        and instrument_info.get("settlement_period") == "PERPETUAL"
    )


def get_trading_pair_from_instrument(instrument: str) -> str:
    return web_utils.instrument_to_trading_pair(instrument)


def get_instrument_from_trading_pair(trading_pair: str) -> str:
    return web_utils.trading_pair_to_instrument(trading_pair)


def parse_instrument_info(instrument_info: Dict[str, Any]) -> Dict[str, Any]:
    """Parse raw instrument info into standardized format."""
    instrument = instrument_info.get("instrument", "")
    base = instrument_info.get("base", "")
    quote = instrument_info.get("quote", "")
    tick_size = instrument_info.get("tick_size", "0.01")
    min_size = instrument_info.get("min_size", "0.001")

    return {
        "trading_pair": web_utils.instrument_to_trading_pair(instrument),
        "instrument": instrument,
        "base_asset": base,
        "quote_asset": quote,
        "min_order_size": Decimal(str(min_size)),
        "tick_size": Decimal(str(tick_size)),
        "step_size": Decimal(str(min_size)),
        "base_decimals": instrument_info.get("base_decimals", 9),
        "quote_decimals": instrument_info.get("quote_decimals", 6),
    }


def order_side_to_grvt(is_buy: bool) -> bool:
    """Convert Hummingbot buy/sell to GRVT isBuyingContract."""
    return is_buy


def grvt_order_status_to_hummingbot(grvt_status: str):
    """Map GRVT order status string to Hummingbot OrderState."""
    from hummingbot.core.data_type.in_flight_order import OrderState
    status_map = {
        "OPEN": OrderState.OPEN,
        "PENDING": OrderState.OPEN,
        "FILLED": OrderState.FILLED,
        "CANCELLED": OrderState.CANCELED,
        "REJECTED": OrderState.FAILED,
        "EXPIRED": OrderState.CANCELED,
    }
    return status_map.get(grvt_status.upper(), OrderState.OPEN)


class GrvtPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="grvt_perpetual", const=True, client_data=None)

    grvt_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your GRVT API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    grvt_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your GRVT Ethereum private key (for EIP-712 signing)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    grvt_trading_account_id: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your GRVT trading account ID",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "grvt_perpetual"


KEYS = GrvtPerpetualConfigMap.construct()
OTHER_DOMAINS = [CONSTANTS.TESTNET_DOMAIN]
OTHER_DOMAINS_PARAMETER = {CONSTANTS.TESTNET_DOMAIN: CONSTANTS.TESTNET_DOMAIN}
OTHER_DOMAINS_EXAMPLE_PAIR = {CONSTANTS.TESTNET_DOMAIN: "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {CONSTANTS.TESTNET_DOMAIN: DEFAULT_FEES}


class GrvtPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default=CONSTANTS.TESTNET_DOMAIN, const=True, client_data=None)

    grvt_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your GRVT Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    grvt_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your GRVT Testnet Ethereum private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    grvt_trading_account_id: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your GRVT Testnet trading account ID",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = CONSTANTS.TESTNET_DOMAIN


OTHER_DOMAINS_KEYS = {CONSTANTS.TESTNET_DOMAIN: GrvtPerpetualTestnetConfigMap.construct()}
