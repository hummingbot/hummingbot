from typing import (
    List,
    Tuple,
)
from hummingbot.strategy.dev_0_hello_world.dev_0_hello_world_config_map import dev_0_hello_world_config_map
from hummingbot.client.settings import EXAMPLE_PAIRS
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.dev_0_hello_world import HelloWorldStrategy


def start(self):
    try:
        market = dev_0_hello_world_config_map.get("market").value.lower()
        asset_symbol = dev_0_hello_world_config_map.get("asset_symbol").value

        try:
            symbol_pair = EXAMPLE_PAIRS.get(market)
            assets: Tuple[str, str] = self._initialize_market_assets(market, [symbol_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [symbol_pair])]

        self._initialize_wallet(token_symbols=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], symbol_pair] + list(assets)
        self.market_symbol_pairs = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = HelloWorldStrategy.OPTION_LOG_ALL

        self.strategy = HelloWorldStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                           asset_symbol=asset_symbol,
                                           logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
