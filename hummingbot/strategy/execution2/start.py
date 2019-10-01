from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.execution2 import (
    Execution2Strategy
)
from hummingbot.strategy.execution2.execution2_config_map import execution2_config_map


def start(self):
    try:
        market = execution2_config_map.get("market").value.lower()
        raw_market_symbol = execution2_config_map.get("market_symbol_pair").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(market, [raw_market_symbol])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [raw_market_symbol])]

        self._initialize_wallet(token_symbols=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], raw_market_symbol] + list(assets)
        self.market_symbol_pairs = [MarketSymbolPair(*maker_data)]

        strategy_logging_options = Execution2Strategy.OPTION_LOG_ALL

        self.strategy = Execution2Strategy(market_infos=[MarketSymbolPair(*maker_data)],
                                           logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
