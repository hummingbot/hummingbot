from decimal import Decimal

from hummingbot.core.data_type.common import OrderType

# Polymarket API endpoints (confirmed working from poly-maker and py-clob-client)
REST_BASE_URL = "https://clob.polymarket.com"
WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
WS_USER_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"

# REST API endpoints - will use py-clob-client SDK methods instead of direct calls
REST_API_VERSION = "v1"
API_BASE_URL = f"{REST_BASE_URL}/{REST_API_VERSION}"

ORDERS_URL = f"{API_BASE_URL}/orders"
TRADES_URL = f"{API_BASE_URL}/trades"
MARKETS_URL = f"{API_BASE_URL}/markets"
BOOK_URL = f"{API_BASE_URL}/book"
TICKER_URL = f"{API_BASE_URL}/ticker"
BALANCE_URL = f"{API_BASE_URL}/balance"
POSITIONS_URL = f"{API_BASE_URL}/positions"

# Default fees (from Polymarket docs - example rates)
DEFAULT_MAKER_FEE = Decimal("0.02")  # 2%
DEFAULT_TAKER_FEE = Decimal("0.07")  # 7%

# Order type flags mapping (from py-clob-client SDK)
POST_ONLY_FLAG = "post_only"
IOC_FLAG = "ioc"  # Will be mapped to FAK in SDK
FOK_FLAG = "fok"

# SDK Order Type Mapping (hummingbot OrderType -> py-clob-client OrderType)
SDK_ORDER_TYPE_MAPPING = {
    OrderType.LIMIT: "GTC",
    OrderType.LIMIT_MAKER: "GTC",  # Will use post-only option
    OrderType.IOC: "FAK",  # Fill and Kill = Immediate or Cancel
    OrderType.FOK: "FOK",  # Fill or Kill
    OrderType.PREDICTION_LIMIT: "GTC",
    OrderType.PREDICTION_MARKET: "FOK"  # Use FOK for market orders
}

# WebSocket channels
WS_CHANNEL_USER = "USER"
WS_CHANNEL_MARKET = "MARKET"

# Signature types for EIP-712
SIGNATURE_TYPE_EOA = 0
SIGNATURE_TYPE_POLY_PROXY = 1
SIGNATURE_TYPE_POLY_GNOSIS = 2

# Blockchain configuration
CHAIN_ID = 137  # Polygon
POLYGON_CHAIN_ID = 137  # Alias for consistency with auth module

# Authentication endpoints
AUTH_DERIVE_API_KEY_URL = f"{REST_BASE_URL}/auth/derive-api-key"
AUTH_CREATE_API_KEY_URL = f"{REST_BASE_URL}/auth/api-key"
AUTH_GET_API_KEYS_URL = f"{REST_BASE_URL}/auth/api-keys"
AUTH_DELETE_API_KEY_URL = f"{REST_BASE_URL}/auth/api-key"

# Order placement (requires L1 auth)
ORDER_PLACEMENT_URL = f"{REST_BASE_URL}/exchange"

# Smart contract addresses (from py-clob-client and poly-maker)
EXCHANGE_CONTRACT = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
NEG_RISK_MARKETS_CONTRACT = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

# Order and trade states
ORDER_STATE_SUBMITTED = "SUBMITTED"
ORDER_STATE_MATCHED = "MATCHED"
ORDER_STATE_MINED = "MINED"
ORDER_STATE_CONFIRMED = "CONFIRMED"
ORDER_STATE_CANCELLED = "CANCELLED"

# Rate limiting
RATE_LIMIT_REQUESTS_PER_SECOND = 10
REQUEST_TIMEOUT = 30

# Trading pair format: MARKET-OUTCOME-QUOTE (canonical hyphen format)
OUTCOME_YES = "YES"
OUTCOME_NO = "NO"
QUOTE_ASSET = "USDC"

# Risk management constants (from poly-maker best practices)
MIN_ACCEPTABLE_PRICE = Decimal("0.1")
MAX_ACCEPTABLE_PRICE = Decimal("0.9")
PRICE_CHANGE_THRESHOLD = Decimal("0.005")  # 0.5 cents
SIZE_CHANGE_THRESHOLD_PCT = Decimal("0.1")  # 10%
