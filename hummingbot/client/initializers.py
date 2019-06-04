from typing import (
    List,
    Tuple,
)

from hummingbot.market.market_base import MarketBase
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket
from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket

name_to_market_class_mapping = {
    "bamboo_relay": BambooRelayMarket,
    "binance": BinanceMarket,
    "coinbase_pro": CoinbaseProMarket,
    "ddex": DDEXMarket,
    "radar_relay": RadarRelayMarket,
}


def get_market_class_by_name(market_name: str):
    return name_to_market_class_mapping.get(market_name, MarketBase)


def initialize_market_assets(market_name: str, symbols: List[str]):
    market: MarketBase = get_market_class_by_name(market_name)
    market_symbols: List[Tuple[str, str]] = [market.split_symbol(symbol) for symbol in symbols]
    return market_symbols


