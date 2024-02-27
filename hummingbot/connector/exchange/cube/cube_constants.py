EXCHANGE_NAME = "cube"

DEFAULT_DOMAIN = "live"
TESTNET_DOMAIN = "staging"

# Base URL
REST_URLS = {"live": "https://api.cube.exchange",
             "staging": "https://staging.cube.exchange"}

WSS_MARKET_DATA_URL = {"live": "wss://api.cube.exchange/md",
                       "staging": "wss://staging.cube.exchange/md"}

WSS_TRADE_URL = {"live": "wss://api.cube.exchange/os",
                 "staging": "wss://api.cube.exchange/os"}
