from hummingbot.core.api_throttler.data_types import RateLimit

DEFAULT_DOMAIN = "chainflip_lp"
EXCHANGE_NAME = "chainflip_lp"

REST_RPC_URLS = {
    "chainflip_lp": "https://mainnet-rpc.chainflip.io",
    "chainflip_lp_testnet": "https://archive.perseverance.chainflip.io",
}
WS_RPC_URLS = {
    "chainflip_lp": "wss://mainnet-rpc.chainflip.io",
    "chainflip_lp_testnet": "wss://archive.perseverance.chainflip.io",
}
WS_HEARTBEAT_TIME_INTERVAL = 30

LISTENER_TIME_INTERVAL = 10

MAX_REQUEST = 1000
SECOND = 1
MAX_ID_LEN = (2**64) - 1


# Public chainflip lp rpc methods
ACTIVE_POOLS_METHOD = "cf_pool_environment"
ASSET_BALANCE_METHOD = "lp_free_balances"
PING_METHOD = ""
OPEN_ORDERS_METHOD = "cf_pool_orders"
PLACE_LIMIT_ORDER_METHOD = "lp_set_limit_order"
CANCEL_LIMIT_ORDER = "lp_set_limit_order"  # set
MY_TRADES_METHOD = ""
POOL_ORDERBOOK_METHOD = "cf_pool_orderbook"
SUPPORTED_ASSETS_METHOD = "cf_supported_assets"
ORDER_FILLS_SUBSCRIPTION_METHOD = "lp_subscribe_order_fills"
ORDER_FILLS_METHOD = "lp_order_fills"
MARKET_PRICE_METHOD = "cf_pool_price"
MARKET_PRICE_V2_METHOD = "cf_pool_price_v2"
SCHEDULED_SWAPS = "cf_subscribe_scheduled_swaps"

CLIENT_ID_PREFIX = ""

# chainflip params
SIDE_BUY = "buy"
SIDE_SELL = "sell"

# rate limit id
GENERAL_LIMIT_ID = "General"


RATE_LIMITS = [RateLimit(GENERAL_LIMIT_ID, MAX_REQUEST, SECOND)]

ASSET_PRECISIONS = {
    "Ethereum": {
        "USDC": 1e6,
        "USDT": 1e6,
        "FLIP": 1e18,
        "ETH": 1e18,
    },
    "Arbitrum": {"USDC": 1e6, "USDT": 1e6, "ETH": 1e18},
    "Bitcoin": {"BTC": 1e8},
    "Polkadot": {"DOT": 1e12},
    "Solana": {"SOL": 1e9, "USDC": 1e6},
}

FRACTIONAL_BITS = 128
SQRT_PRICE_FRACTIONAL_BITS = 96
LOWER_TICK_BOUND = -887272
UPPER_TICK_BOUND = 887272

SAME_CHAINS = {"ETH": ["Arbitrum", "Ethereum"], "USDC": ["Arbitrum", "Ethereum", "Solana"]}
DEFAULT_CHAIN_CONFIG = {"ETH": "Ethereum", "USDC": "Ethereum"}
