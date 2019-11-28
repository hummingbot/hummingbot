# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "Bitcoin.com"
# EXCHANGE_NAME_CAMEL = "BitcoinCom"

REST_URL = "https://api.exchange.bitcoin.com/api/2"
REST_MARKETS_URL = f"{REST_URL}/public/symbol"
REST_TICKERS_URL = f"{REST_URL}/public/ticker"
REST_ORDERBOOK_URL = f"{REST_URL}/public/orderbook"

WSS_URL = "wss://api.exchange.bitcoin.com/api/2/ws"
