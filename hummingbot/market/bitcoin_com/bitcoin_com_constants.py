# A single source of truth for constant variables related to the exchange

from hummingbot.market.bitcoin_com.bitcoin_com_utils import join_paths


EXCHANGE_NAME = "bitcoin_com"

REST_URL = "https://api.exchange.bitcoin.com/api/2"
REST_MARKETS_URL = join_paths(REST_URL, "public/symbol")
REST_TICKERS_URL = join_paths(REST_URL, "public/ticker")
REST_ORDERBOOK_URL = join_paths(REST_URL, "public/orderbook")
REST_CURRENCY_URL = join_paths(REST_URL, "public/currency")
REST_BALANCE_URL = join_paths(REST_URL, "trading/balance")

WSS_URL = "wss://api.exchange.bitcoin.com/api/2/ws"
