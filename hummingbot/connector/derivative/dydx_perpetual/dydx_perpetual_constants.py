# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "dydx_perpetual"

API_VERSION = "v3"

# API Base URLs
DYDX_REST_URL = "https://api.dydx.exchange/{}".format(API_VERSION)
DYDX_WS_URL = "wss://api.dydx.exchange/{}/ws".format(API_VERSION)


# Public REST Endpoints

MARKETS_URL = "/markets"
TICKER_URL = "/stats"
SNAPSHOT_URL = "/orderbook/"
