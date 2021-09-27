from decimal import Decimal
from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.base_price_action.base_price_action import BasePriceActionStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.base_price_action.base_price_action_config_map import base_price_action_config_map


def start(self):
    try:
        min_order_amount = base_price_action_config_map.get("min_order_amount").value
        max_order_amount = base_price_action_config_map.get("max_order_amount").value
        time_delay = base_price_action_config_map.get("time_delay").value
        market = base_price_action_config_map.get("market").value.lower()
        raw_market_trading_pair = base_price_action_config_map.get("market_trading_pair_tuple").value
        percentage_of_price_change = base_price_action_config_map.get("percentage_of_price_change").value
        trade_bands = base_price_action_config_map.get("trade_bands").value

        cancel_order_wait_time = base_price_action_config_map.get("cancel_order_wait_time").value

        trade_bands = trade_bands.replace(" ", "")
        trade_bands = [tuple(band.split(":")) for band in trade_bands.split(";")]
        trade_bands = list(map(lambda x: (float(x[0]), Decimal(x[1])), trade_bands))

        try:
            trading_pair: str = raw_market_trading_pair
            assets: Tuple[str, str] = self._initialize_market_assets(market, [trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [trading_pair])]

        self._initialize_wallet(token_trading_pairs=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = BasePriceActionStrategy.OPTION_LOG_ALL

        self.strategy = BasePriceActionStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                                cancel_order_wait_time=cancel_order_wait_time,
                                                time_delay=time_delay,
                                                min_order_amount=min_order_amount,
                                                max_order_amount=max_order_amount,
                                                logging_options=strategy_logging_options,
                                                percentage_of_price_change=percentage_of_price_change,
                                                trade_bands=trade_bands
                                                )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
