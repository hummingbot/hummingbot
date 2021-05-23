from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.dca import (
    DCATradeStrategy
)
from hummingbot.strategy.dca.dca_config_map import dca_config_map


def start(self):
    try:
        order_amount = dca_config_map.get("order_amount").value
        days_period = dca_config_map.get("days_period").value
        num_individual_orders = dca_config_map.get("num_individual_orders").value
        market = dca_config_map.get("market").value.lower()
        raw_market_trading_pair = dca_config_map.get("market_trading_pair_tuple").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(market, [raw_market_trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return



        market_names: List[Tuple[str, List[str]]] = [(market, [raw_market_trading_pair])]

        self._initialize_wallet(token_trading_pairs=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], raw_market_trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = DCATradeStrategy.OPTION_LOG_ALL

        self.strategy = DCATradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                              days_period=days_period,
                                              num_individual_orders = num_individual_orders,
                                              order_amount=order_amount,
                                              logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
