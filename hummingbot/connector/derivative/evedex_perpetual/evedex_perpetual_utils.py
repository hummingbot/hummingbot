from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# EVEDEX fees from /api/market: maker=0.015%, taker=0.045%
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),
    taker_percent_fee_decimal=Decimal("0.00045"),
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"

SIDE_BUY = "buy"
SIDE_SELL = "sell"


def is_exchange_information_valid(instrument: Dict[str, Any]) -> bool:
    return web_utils.is_instrument_active(instrument)


def parse_instrument_info(instrument: Dict[str, Any]) -> Dict[str, Any]:
    instrument_id = instrument.get("id", "")
    from_coin = instrument.get("from", {})
    to_coin = instrument.get("to", {})

    base = from_coin.get("symbol", "").upper()
    quote = to_coin.get("symbol", "").upper()
    trading_pair = web_utils.instrument_to_trading_pair(instrument_id)

    min_qty = Decimal(str(instrument.get("minQuantity", "0.001")))
    max_qty = Decimal(str(instrument.get("maxQuantity", "500")))
    qty_increment = Decimal(str(instrument.get("quantityIncrement", "0.001")))
    price_increment = Decimal(str(instrument.get("priceIncrement", "0.1")))
    min_volume = Decimal(str(instrument.get("minVolume", "5")))

    return {
        "trading_pair": trading_pair,
        "instrument_id": instrument_id,
        "base_asset": base,
        "quote_asset": quote,
        "min_order_size": min_qty,
        "max_order_size": max_qty,
        "step_size": qty_increment,
        "tick_size": price_increment,
        "min_notional": min_volume,
        "max_leverage": instrument.get("maxLeverage", 100),
        "last_price": Decimal(str(instrument.get("lastPrice", "0"))),
        "mark_price": Decimal(str(instrument.get("markPrice", "0"))),
    }


def order_status_to_hummingbot(status: str):
    from hummingbot.core.data_type.in_flight_order import OrderState
    return CONSTANTS.ORDER_STATE.get(status.upper(), OrderState.OPEN)


class EvedexPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="evedex_perpetual", const=True, client_data=None)

    evedex_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ethereum private key for EVEDEX (used for EIP-712 signing)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "evedex_perpetual"


KEYS = EvedexPerpetualConfigMap.construct()
OTHER_DOMAINS = [CONSTANTS.TESTNET_DOMAIN]
OTHER_DOMAINS_PARAMETER = {CONSTANTS.TESTNET_DOMAIN: CONSTANTS.TESTNET_DOMAIN}
OTHER_DOMAINS_EXAMPLE_PAIR = {CONSTANTS.TESTNET_DOMAIN: "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {CONSTANTS.TESTNET_DOMAIN: DEFAULT_FEES}


class EvedexPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default=CONSTANTS.TESTNET_DOMAIN, const=True, client_data=None)

    evedex_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ethereum private key for EVEDEX Testnet",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = CONSTANTS.TESTNET_DOMAIN


OTHER_DOMAINS_KEYS = {CONSTANTS.TESTNET_DOMAIN: EvedexPerpetualTestnetConfigMap.construct()}
