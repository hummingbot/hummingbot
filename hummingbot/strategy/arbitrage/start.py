from typing import (
    List,
    Tuple,
)
from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from hummingbot.strategy.arbitrage.arbitrage_config_map import arbitrage_config_map


def start(self):
    primary_market = arbitrage_config_map.get("primary_market").value.lower()
    secondary_market = arbitrage_config_map.get("secondary_market").value.lower()
    raw_primary_trading_pair = arbitrage_config_map.get("primary_market_trading_pair").value
    raw_secondary_trading_pair = arbitrage_config_map.get("secondary_market_trading_pair").value
    min_profitability = arbitrage_config_map.get("min_profitability").value / Decimal("100")
    use_oracle_conversion_rate = arbitrage_config_map.get("use_oracle_conversion_rate").value
    secondary_to_primary_base_conversion_rate = arbitrage_config_map["secondary_to_primary_base_conversion_rate"].value
    secondary_to_primary_quote_conversion_rate = arbitrage_config_map["secondary_to_primary_quote_conversion_rate"].value

    try:
        primary_trading_pair: str = raw_primary_trading_pair
        secondary_trading_pair: str = raw_secondary_trading_pair
        primary_assets: Tuple[str, str] = self._initialize_market_assets(primary_market, [primary_trading_pair])[0]
        secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_market,
                                                                           [secondary_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [(primary_market, [primary_trading_pair]),
                                                 (secondary_market, [secondary_trading_pair])]
    self._initialize_markets(market_names)

    primary_data = [self.markets[primary_market], primary_trading_pair] + list(primary_assets)
    secondary_data = [self.markets[secondary_market], secondary_trading_pair] + list(secondary_assets)
    self.market_trading_pair_tuples = [MarketTradingPairTuple(*primary_data), MarketTradingPairTuple(*secondary_data)]
    self.market_pair = ArbitrageMarketPair(*self.market_trading_pair_tuples)
    self.strategy = ArbitrageStrategy()
    self.strategy.init_params(market_pairs=[self.market_pair],
                              min_profitability=min_profitability,
                              logging_options=ArbitrageStrategy.OPTION_LOG_ALL,
                              use_oracle_conversion_rate=use_oracle_conversion_rate,
                              secondary_to_primary_base_conversion_rate=secondary_to_primary_base_conversion_rate,
                              secondary_to_primary_quote_conversion_rate=secondary_to_primary_quote_conversion_rate,
                              hb_app_notification=True)
