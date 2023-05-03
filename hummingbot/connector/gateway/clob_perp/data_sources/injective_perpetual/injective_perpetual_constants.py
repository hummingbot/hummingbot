from configparser import ConfigParser
from decimal import Decimal
from typing import Dict, Tuple

from pyinjective.constant import (
    Network,
    devnet_config as DEVNET_TOKEN_META_CONFIG,
    mainnet_config as MAINNET_TOKEN_META_CONFIG,
    testnet_config as TESTNET_TOKEN_META_CONFIG,
)

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

CONNECTOR_NAME = "injective_perpetual"
LOST_ORDER_COUNT_LIMIT = 3
ORDER_CHAIN_PROCESSING_TIMEOUT = 5

DEFAULT_SUB_ACCOUNT_SUFFIX = "000000000000000000000000"

NETWORK_CONFIG = {
    "mainnet": Network.mainnet(node="k8s"),
    "testnet": Network.testnet(),
    "devnet": Network.devnet()
}

MARKETS_UPDATE_INTERVAL = 8 * 60 * 60

SUPPORTED_ORDER_TYPES = [OrderType.LIMIT, OrderType.LIMIT_MAKER]
SUPPORTED_POSITION_MODES = [PositionMode.ONEWAY]

MSG_CREATE_DERIVATIVE_LIMIT_ORDER = "/injective.exchange.v1beta1.MsgCreateDerivativeLimitOrder"
MSG_CANCEL_DERIVATIVE_ORDER = "/injective.exchange.v1beta1.MsgCancelDerivativeOrder"
MSG_BATCH_UPDATE_ORDERS = "/injective.exchange.v1beta1.MsgBatchUpdateOrders"

INJ_DERIVATIVE_TX_EVENT_TYPES = [
    MSG_CREATE_DERIVATIVE_LIMIT_ORDER,
    MSG_CANCEL_DERIVATIVE_ORDER,
    MSG_BATCH_UPDATE_ORDERS,
]

INJ_DERIVATIVE_ORDER_STATES = {
    "booked": OrderState.OPEN,
    "partial_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
}

CLIENT_TO_BACKEND_ORDER_TYPES_MAP: Dict[Tuple[TradeType, OrderType], str] = {
    (TradeType.BUY, OrderType.LIMIT): "buy",
    (TradeType.BUY, OrderType.LIMIT_MAKER): "buy_po",
    (TradeType.BUY, OrderType.MARKET): "take_buy",
    (TradeType.SELL, OrderType.LIMIT): "sell",
    (TradeType.SELL, OrderType.LIMIT_MAKER): "sell_po",
    (TradeType.SELL, OrderType.MARKET): "take_sell",
}

FETCH_ORDER_HISTORY_LIMIT = 100

BASE_GAS = Decimal("100e3")
GAS_BUFFER = Decimal("20e3")
DERIVATIVE_SUBMIT_ORDER_GAS = Decimal("45e3")
DERIVATIVE_CANCEL_ORDER_GAS = Decimal("25e3")


def _parse_network_config_to_denom_meta(config: ConfigParser):
    """
    Parses token's denom configuration from Injective SDK.
    i.e.
    {
        "inj": {
            "symbol": "INJ",
            "decimal": 18
        },
        "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7": {
            "symbol": "USDT",
            "decimal": 6
        },
    }
    """
    return {
        entry["peggy_denom"]: {"symbol": entry.name, "decimal": entry["decimals"]}
        for entry in config.values() if "peggy_denom" in entry
    }


NETWORK_DENOM_TOKEN_META = {
    "mainnet": _parse_network_config_to_denom_meta(config=MAINNET_TOKEN_META_CONFIG),
    "testnet": _parse_network_config_to_denom_meta(config=TESTNET_TOKEN_META_CONFIG),
    "devnet": _parse_network_config_to_denom_meta(config=DEVNET_TOKEN_META_CONFIG)
}

GLOBAL_LIMIT_ID = "GlobalLimitID"
GLOBAL_LIMIT = 5
PING_LIMIT_ID = "PingLimitID"
PING_LIMIT = GLOBAL_LIMIT
ORDER_BOOK_LIMIT_ID = "OrderBookLimitID"
ORDER_BOOK_LIMIT = GLOBAL_LIMIT
POSITIONS_LIMIT_ID = "PositionsLimitID"
POSITIONS_LIMIT = GLOBAL_LIMIT
ACCOUNT_PORTFOLIO_LIMIT_ID = "AccountPortfolioLimitID"
ACCOUNT_PORTFOLIO_LIMIT = GLOBAL_LIMIT
FUNDING_PAYMENT_LIMIT_ID = "GetFundingPaymentLimitID"
FUNDING_PAYMENT_LIMIT = GLOBAL_LIMIT
ACCOUNT_LIMIT_ID = "AccountLimitID"
ACCOUNT_LIMIT = GLOBAL_LIMIT
SYNC_TIMEOUT_HEIGHT_LIMIT_ID = "SyncTimeoutHeightLimitID"
SYNC_TIMEOUT_HEIGHT_LIMIT = GLOBAL_LIMIT
DERIVATIVE_MARKETS_LIMIT_ID = "DerivativeMarketsLimitID"
DERIVATIVE_MARKETS_LIMIT = GLOBAL_LIMIT
SINGLE_DERIVATIVE_MARKET_LIMIT_ID = "SingleDerivativeMarketLimitID"
SINGLE_DERIVATIVE_MARKET_LIMIT = GLOBAL_LIMIT
SPOT_MARKETS_LIMIT_ID = "SpotMarketsLimitID"
SPOT_MARKETS_LIMIT = GLOBAL_LIMIT
HISTORICAL_DERIVATIVE_ORDERS_LIMIT_ID = "HistoricalDerivativeOrdersLimitID"
HISTORICAL_DERIVATIVE_ORDERS_LIMIT = GLOBAL_LIMIT
DERIVATIVE_TRADES_LIMIT_ID = "DerivativeTradesLimitID"
DERIVATIVE_TRADES_LIMIT = GLOBAL_LIMIT
TRANSACTION_BY_HASH_LIMIT_ID = "TransactionByHashLimitID"
TRANSACTION_BY_HASH_LIMIT = GLOBAL_LIMIT
FUNDING_RATES_LIMIT_ID = "FundingRatesLimitID"
FUNDING_RATES_LIMIT = GLOBAL_LIMIT
ORACLE_PRICES_LIMIT_ID = "OraclePricesLimitID"
ORACLE_PRICES_LIMIT = GLOBAL_LIMIT

RATE_LIMITS = [
    RateLimit(limit_id=GLOBAL_LIMIT_ID, limit=GLOBAL_LIMIT, time_interval=1),
    RateLimit(
        limit_id=PING_LIMIT_ID,
        limit=PING_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=PING_LIMIT_ID,
        limit=PING_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_LIMIT_ID,
        limit=ORDER_BOOK_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=POSITIONS_LIMIT_ID,
        limit=POSITIONS_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=ACCOUNT_PORTFOLIO_LIMIT_ID,
        limit=ACCOUNT_PORTFOLIO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=FUNDING_PAYMENT_LIMIT_ID,
        limit=FUNDING_PAYMENT_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=ACCOUNT_LIMIT_ID,
        limit=ACCOUNT_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=SYNC_TIMEOUT_HEIGHT_LIMIT_ID,
        limit=SYNC_TIMEOUT_HEIGHT_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=DERIVATIVE_MARKETS_LIMIT_ID,
        limit=DERIVATIVE_MARKETS_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=SINGLE_DERIVATIVE_MARKET_LIMIT_ID,
        limit=SINGLE_DERIVATIVE_MARKET_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=SPOT_MARKETS_LIMIT_ID,
        limit=SPOT_MARKETS_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=HISTORICAL_DERIVATIVE_ORDERS_LIMIT_ID,
        limit=HISTORICAL_DERIVATIVE_ORDERS_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=DERIVATIVE_TRADES_LIMIT_ID,
        limit=DERIVATIVE_TRADES_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=TRANSACTION_BY_HASH_LIMIT_ID,
        limit=TRANSACTION_BY_HASH_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=FUNDING_RATES_LIMIT_ID,
        limit=FUNDING_RATES_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=ORACLE_PRICES_LIMIT_ID,
        limit=ORACLE_PRICES_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_LIMIT_ID, weight=1)],
    ),
]
