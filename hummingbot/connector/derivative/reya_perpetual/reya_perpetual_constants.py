from hummingbot.core.api_throttler.data_types import RateLimit

DEFAULT_DOMAIN = "reya_perpetual"
TESTNET_DOMAIN = "reya_perpetual_testnet"

# The testnet domain is Reya's devnet, the network listed for Perp OB integrations.
REST_URLS = {DEFAULT_DOMAIN: "https://api.reya.xyz/", TESTNET_DOMAIN: "https://api-devnet.reya-cronos.network/"}
WS_URLS = {DEFAULT_DOMAIN: "wss://ws.reya.xyz", TESTNET_DOMAIN: "wss://websocket-devnet.reya-cronos.network"}
CHAIN_IDS = {DEFAULT_DOMAIN: 1729, TESTNET_DOMAIN: 89346162}
# OrdersGateway proxy: the EIP-712 verifying contract.
ORDERS_GATEWAYS = {
    DEFAULT_DOMAIN: "0xfc8c96be87da63cecddbf54abfa7b13ee8044739",
    TESTNET_DOMAIN: "0x7Ec89E555c771D2B5939aBE5C4E4291852633D4D",
}
EXCHANGE_ID = 2
COLLATERAL_TOKEN = "RUSD"
SYMBOL_SUFFIX = "RUSDPERP"

V2_PATH = "v2/"
# The v2 API has no signer-permission read yet; the app's trading API provides it.
API_WALLET_STATUS_PATH = "api/trading/wallet/{address}/apiWalletStatus"

MARKETS_PATH = "perpMarketDefinitions"
MARKET_SUMMARY_PATH = "perpMarket/{symbol}/summary"
DEPTH_PATH = "market/{symbol}/depth"
FEE_TIERS_PATH = "feeTiers"
WALLET_PATH = "wallet/{address}/{resource}"
CREATE_ORDER_PATH = "createOrder"
CANCEL_ORDER_PATH = "cancelOrder"

DEPTH_LEVELS = 100
HISTORY_PAGE_LIMIT = 100
HISTORY_MAX_PAGES = 5
MARKET_ORDER_SLIPPAGE = "0.005"
SIGNATURE_DEADLINE = 30

ORDER_STATE = {"OPEN": "OPEN", "FILLED": "FILLED", "CANCELLED": "CANCELED"}
ORDER_OUTCOME_UNKNOWN_ERROR = "ORDER_OUTCOME_UNKNOWN_ERROR"
SERVICE_UNAVAILABLE_ERROR = "SERVICE_UNAVAILABLE_ERROR"
ORDER_NOT_FOUND_ERROR = "ORDER_NOT_FOUND_ERROR"

RATE_LIMIT_ID = "REYA_REST"
# Conservative shared budget; server-side per-account limits still apply.
RATE_LIMITS = [RateLimit(limit_id=RATE_LIMIT_ID, limit=5, time_interval=1)]
