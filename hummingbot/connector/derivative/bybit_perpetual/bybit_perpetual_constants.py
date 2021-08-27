# A single source of truth for constant variables related to the exchange
from typing import List, Optional

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils import (
    NON_LINEAR_MARKET, LINEAR_MARKET, get_rest_api_market_for_endpoint, get_pair_specific_limit_id
)

EXCHANGE_NAME = "bybit_perpetual"

REST_URLS = {"bybit_perpetual_main": "https://api.bybit.com/",
             "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"}
WSS_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime",
            "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime"}

REST_API_VERSION = "v2"

# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/tickers",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/tickers"}
QUERY_SYMBOL_ENDPOINT = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/symbols",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/symbols"}
ORDER_BOOK_ENDPOINT = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/orderBook/L2",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/orderBook/L2"}

# REST API Private Endpoints
SET_LEVERAGE_PATH_URL = {
    LINEAR_MARKET: "private/linear/position/set-leverage",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/position/leverage/save"}
GET_LAST_FUNDING_RATE_PATH_URL = {
    LINEAR_MARKET: "private/linear/funding/prev-funding",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/funding/prev-funding"}
GET_POSITIONS_PATH_URL = {
    LINEAR_MARKET: "private/linear/position/list",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/position/list"}
PLACE_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/create",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/create"}
CANCEL_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/cancel",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/cancel"}
QUERY_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/search",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order"}
USER_TRADE_RECORDS_PATH_URL = {
    LINEAR_MARKET: "private/linear/trade/execution/list",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/execution/list"}
GET_WALLET_BALANCE_PATH_URL = {
    LINEAR_MARKET: f"{REST_API_VERSION}/private/wallet/balance",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/wallet/balance"}

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "position"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "order"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "execution"

NON_LINEAR_GET_LIMIT_ID = "NonLinearGETLimit"
NON_LINEAR_POST_LIMIT_ID = "NonLinearPOSTLimit"
LINEAR_GET_LIMIT_ID = "LinearGETLimit"
LINEAR_POST_LIMIT_ID = "LinearPOSTLimit"
GET_RATE = 49  # per second
POST_RATE = 19  # per second

NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "NonLinearPrivateBucket100"
NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "NonLinearPrivateBucket600"
NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "NonLinearPrivateBucket75"
NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID = "NonLinearPrivateBucket120A"
NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID = "NonLinearPrivateBucket120B"

LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "LinearPrivateBucket100"
LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "LinearPrivateBucket600"
LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "LinearPrivateBucket75"
LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID = "LinearPrivateBucket120A"


def build_rate_limits(trading_pairs: Optional[List[str]] = None) -> List[RateLimit]:
    trading_pairs = trading_pairs or []
    rate_limits = []

    rate_limits.extend(_build_global_rate_limits())
    rate_limits.extend(_build_public_rate_limits(trading_pairs))
    rate_limits.extend(_build_private_rate_limits(trading_pairs))

    return rate_limits


def _build_global_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(limit_id=NON_LINEAR_GET_LIMIT_ID, limit=GET_RATE, time_interval=1),
        RateLimit(limit_id=NON_LINEAR_POST_LIMIT_ID, limit=POST_RATE, time_interval=1),
        RateLimit(limit_id=LINEAR_GET_LIMIT_ID, limit=GET_RATE, time_interval=1),
        RateLimit(limit_id=LINEAR_POST_LIMIT_ID, limit=POST_RATE, time_interval=1),
    ]
    return rate_limits


def _build_public_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    rate_limits.extend(_build_public_pair_specific_rate_limits(trading_pairs))
    rate_limits.extend(_build_public_general_rate_limits())

    return rate_limits


def _build_public_pair_specific_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    for trading_pair in trading_pairs:
        limit_id = get_pair_specific_limit_id(
            base_limit_id=LATEST_SYMBOL_INFORMATION_ENDPOINT[NON_LINEAR_MARKET],  # same for linear and non-linear
            trading_pair=trading_pair,
        )
        rate_limits.append(
            RateLimit(
                limit_id=limit_id,
                limit=GET_RATE,
                time_interval=1,
                linked_limits=[NON_LINEAR_GET_LIMIT_ID],
            )
        )

    return rate_limits


def _build_public_general_rate_limits():
    public_rate_limits = [
        RateLimit(
            limit_id=LATEST_SYMBOL_INFORMATION_ENDPOINT[NON_LINEAR_MARKET],  # same for linear and non-linear
            limit=GET_RATE,
            time_interval=1,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID],
        ),
        RateLimit(
            limit_id=QUERY_SYMBOL_ENDPOINT[NON_LINEAR_MARKET],  # same for linear and non-linear
            limit=GET_RATE,
            time_interval=1,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID],
        ),
        RateLimit(
            limit_id=ORDER_BOOK_ENDPOINT[NON_LINEAR_MARKET],  # same for linear and non-linear
            limit=GET_RATE,
            time_interval=1,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID],
        ),
    ]
    return public_rate_limits


def _build_private_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    rate_limits.extend(_build_private_pair_specific_rate_limits(trading_pairs))
    rate_limits.extend(_build_private_general_rate_limits())

    return rate_limits


def _build_private_pair_specific_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    for trading_pair in trading_pairs:
        market = get_rest_api_market_for_endpoint(trading_pair)
        if market == NON_LINEAR_MARKET:
            rate_limits.extend(_build_private_pair_specific_non_linear_rate_limits(trading_pair))
        else:
            rate_limits.extend(_build_private_pair_specific_linear_rate_limits(trading_pair))

    return rate_limits


def _build_private_pair_specific_non_linear_rate_limits(trading_pair: str) -> List[RateLimit]:
    pair_specific_non_linear_private_bucket_100_limit_id = get_pair_specific_limit_id(
        base_limit_id=NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_600_limit_id = get_pair_specific_limit_id(
        base_limit_id=NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_75_limit_id = get_pair_specific_limit_id(
        base_limit_id=NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_120_a_limit_id = get_pair_specific_limit_id(
        base_limit_id=NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_120_b_limit_id = get_pair_specific_limit_id(
        base_limit_id=NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID, trading_pair=trading_pair
    )

    rate_limits = [
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_100_limit_id, limit=100, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_600_limit_id, limit=600, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_75_limit_id, limit=75, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_120_a_limit_id, limit=120, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_120_b_limit_id, limit=120, time_interval=60),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=SET_LEVERAGE_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=75,
            time_interval=60,
            linked_limits=[NON_LINEAR_POST_LIMIT_ID, pair_specific_non_linear_private_bucket_75_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=GET_LAST_FUNDING_RATE_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID, pair_specific_non_linear_private_bucket_120_b_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=GET_POSITIONS_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID, pair_specific_non_linear_private_bucket_120_a_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=PLACE_ACTIVE_ORDER_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=100,
            time_interval=60,
            linked_limits=[NON_LINEAR_POST_LIMIT_ID, pair_specific_non_linear_private_bucket_100_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CANCEL_ACTIVE_ORDER_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=100,
            time_interval=60,
            linked_limits=[NON_LINEAR_POST_LIMIT_ID, pair_specific_non_linear_private_bucket_100_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=QUERY_ACTIVE_ORDER_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=600,
            time_interval=60,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID, pair_specific_non_linear_private_bucket_600_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=USER_TRADE_RECORDS_PATH_URL[NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID],
        ),
    ]

    return rate_limits


def _build_private_pair_specific_linear_rate_limits(trading_pair: str) -> List[RateLimit]:
    pair_specific_linear_private_bucket_100_limit_id = get_pair_specific_limit_id(
        base_limit_id=LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_linear_private_bucket_600_limit_id = get_pair_specific_limit_id(
        base_limit_id=LINEAR_PRIVATE_BUCKET_600_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_linear_private_bucket_75_limit_id = get_pair_specific_limit_id(
        base_limit_id=LINEAR_PRIVATE_BUCKET_75_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_linear_private_bucket_120_a_limit_id = get_pair_specific_limit_id(
        base_limit_id=LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, trading_pair=trading_pair
    )

    rate_limits = [
        RateLimit(limit_id=pair_specific_linear_private_bucket_100_limit_id, limit=100, time_interval=60),
        RateLimit(limit_id=pair_specific_linear_private_bucket_600_limit_id, limit=600, time_interval=60),
        RateLimit(limit_id=pair_specific_linear_private_bucket_75_limit_id, limit=75, time_interval=60),
        RateLimit(limit_id=pair_specific_linear_private_bucket_120_a_limit_id, limit=120, time_interval=60),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=SET_LEVERAGE_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=75,
            time_interval=60,
            linked_limits=[LINEAR_POST_LIMIT_ID, pair_specific_linear_private_bucket_75_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=GET_LAST_FUNDING_RATE_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LINEAR_GET_LIMIT_ID, pair_specific_linear_private_bucket_120_a_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=GET_POSITIONS_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LINEAR_GET_LIMIT_ID, pair_specific_linear_private_bucket_120_a_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=PLACE_ACTIVE_ORDER_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LINEAR_POST_LIMIT_ID, pair_specific_linear_private_bucket_100_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CANCEL_ACTIVE_ORDER_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LINEAR_POST_LIMIT_ID, pair_specific_linear_private_bucket_100_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=QUERY_ACTIVE_ORDER_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=600,
            time_interval=60,
            linked_limits=[LINEAR_GET_LIMIT_ID, pair_specific_linear_private_bucket_600_limit_id],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=USER_TRADE_RECORDS_PATH_URL[LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LINEAR_GET_LIMIT_ID, pair_specific_linear_private_bucket_120_a_limit_id],
        ),
    ]

    return rate_limits


def _build_private_general_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(
            limit_id=GET_WALLET_BALANCE_PATH_URL[NON_LINEAR_MARKET],  # same for linear and non-linear
            limit=120,
            time_interval=60,
            linked_limits=[NON_LINEAR_GET_LIMIT_ID, NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
        ),
    ]
    return rate_limits
