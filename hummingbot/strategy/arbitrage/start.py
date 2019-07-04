from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from hummingbot.strategy.arbitrage.arbitrage_config_map import arbitrage_config_map


def start(self):
    primary_market = arbitrage_config_map.get("primary_market").value.lower()
    secondary_market = arbitrage_config_map.get("secondary_market").value.lower()
    raw_primary_symbol = arbitrage_config_map.get("primary_market_symbol").value.upper()
    raw_secondary_symbol = arbitrage_config_map.get("secondary_market_symbol").value.upper()
    min_profitability = arbitrage_config_map.get("min_profitability").value
    try:
        primary_assets: Tuple[str, str] = self._initialize_market_assets(primary_market, [raw_primary_symbol])[0]
        secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_market,
                                                                           [raw_secondary_symbol])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [(primary_market, [raw_primary_symbol]),
                                                 (secondary_market, [raw_secondary_symbol])]
    self._initialize_wallet(token_symbols=list(set(primary_assets + secondary_assets)))
    self._initialize_markets(market_names)
    self.assets = set(primary_assets + secondary_assets)

    primary_data = [self.markets[primary_market], raw_primary_symbol] + list(primary_assets)
    secondary_data = [self.markets[secondary_market], raw_secondary_symbol] + list(secondary_assets)
    self.market_symbol_pairs = [MarketSymbolPair(*primary_data), MarketSymbolPair(*secondary_data)]
    self.market_pair = ArbitrageMarketPair(*(primary_data + secondary_data))
    self.strategy = ArbitrageStrategy(market_pairs=[self.market_pair],
                                      min_profitability=min_profitability,
                                      logging_options=ArbitrageStrategy.OPTION_LOG_ALL)
