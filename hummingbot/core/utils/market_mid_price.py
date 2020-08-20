import requests
from decimal import Decimal
from typing import Optional
import cachetools.func
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.kraken.kraken_market import KrakenMarket


BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/bookTicker"
KUCOIN_PRICE_URL = "https://api.kucoin.com/api/v1/market/allTickers"
LIQUID_PRICE_URL = "https://api.liquid.com/products"
BITTREX_PRICE_URL = "https://api.bittrex.com/api/v1.1/public/getmarketsummaries"
KRAKEN_PRICE_URL = "https://api.kraken.com/0/public/Ticker?pair="
COINBASE_PRO_PRICE_URL = "https://api.pro.coinbase.com/products/TO_BE_REPLACED/ticker"


def get_mid_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    if exchange == "binance":
        return binance_mid_price(trading_pair)
    elif exchange == "kucoin":
        return kucoin_mid_price(trading_pair)
    elif exchange == "liquid":
        return liquid_mid_price(trading_pair)
    elif exchange == "bittrex":
        return bittrex_mid_price(trading_pair)
    elif exchange == "kraken":
        return kraken_mid_price(trading_pair)
    elif exchange == "coinbase_pro":
        return coinbase_pro_mid_price(trading_pair)
    else:
        return binance_mid_price(trading_pair)


@cachetools.func.ttl_cache(ttl=10)
def binance_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=BINANCE_PRICE_URL)
    records = resp.json()
    result = None
    for record in records:
        pair = BinanceMarket.convert_from_exchange_trading_pair(record["symbol"])
        if trading_pair == pair and record["bidPrice"] is not None and record["askPrice"] is not None:
            result = (Decimal(record["bidPrice"]) + Decimal(record["askPrice"])) / Decimal("2")
            break
    return result


@cachetools.func.ttl_cache(ttl=10)
def kucoin_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=KUCOIN_PRICE_URL)
    records = resp.json()
    result = None
    for record in records["data"]["ticker"]:
        if trading_pair == record["symbolName"] and record["buy"] is not None and record["sell"] is not None:
            result = (Decimal(record["buy"]) + Decimal(record["sell"])) / Decimal("2")
            break
    return result


@cachetools.func.ttl_cache(ttl=10)
def liquid_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=LIQUID_PRICE_URL)
    records = resp.json()
    result = None
    for record in records:
        pair = f"{record['base_currency']}-{record['quoted_currency']}"
        if trading_pair == pair and record["market_ask"] is not None and record["market_bid"] is not None:
            result = (Decimal(record["market_ask"]) + Decimal(record["market_bid"])) / Decimal("2")
            break
    return result


@cachetools.func.ttl_cache(ttl=10)
def bittrex_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=BITTREX_PRICE_URL)
    records = resp.json()
    result = None
    for record in records["result"]:
        symbols = record["MarketName"].split("-")
        pair = f"{symbols[1]}-{symbols[0]}"
        if trading_pair == pair and record["Bid"] is not None and record["Ask"] is not None:
            result = (Decimal(record["Bid"]) + Decimal(record["Ask"])) / Decimal("2")
            break
    return result


@cachetools.func.ttl_cache(ttl=10)
def kraken_mid_price(trading_pair: str) -> Optional[Decimal]:
    k_pair = KrakenMarket.convert_to_exchange_trading_pair(trading_pair)
    resp = requests.get(url=KRAKEN_PRICE_URL + k_pair)
    resp_json = resp.json()
    if len(resp_json["error"]) == 0:
        for record in resp_json["result"]:  # assume only one pair is received
            record = resp_json["result"][record]
            result = (Decimal(record["a"][0]) + Decimal(record["b"][0])) / Decimal("2")
        return result


@cachetools.func.ttl_cache(ttl=10)
def coinbase_pro_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=COINBASE_PRO_PRICE_URL.replace("TO_BE_REPLACED", trading_pair))
    record = resp.json()
    if "bid" in record and "ask" in record:
        result = (Decimal(record["bid"]) + Decimal(record["ask"])) / Decimal("2")
        return result
