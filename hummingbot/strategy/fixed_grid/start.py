from decimal import Decimal
from typing import List, Tuple

from hummingbot.strategy.fixed_grid import FixedGridStrategy
from hummingbot.strategy.fixed_grid.fixed_grid_config_map import fixed_grid_config_map as c_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    try:
        order_amount = c_map.get("order_amount").value
        order_refresh_time = c_map.get("order_refresh_time").value
        max_order_age = c_map.get("max_order_age").value
        start_order_spread = c_map.get("start_order_spread").value / Decimal('100')
        grid_price_ceiling = c_map.get("grid_price_ceiling").value
        grid_price_floor = c_map.get("grid_price_floor").value
        n_levels = c_map.get("n_levels").value
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        order_optimization_enabled = c_map.get("order_optimization_enabled").value
        ask_order_optimization_depth = c_map.get("ask_order_optimization_depth").value
        bid_order_optimization_depth = c_map.get("bid_order_optimization_depth").value
        order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal('100')

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        take_if_crossed = c_map.get("take_if_crossed").value

        should_wait_order_cancel_confirmation = c_map.get("should_wait_order_cancel_confirmation")

        strategy_logging_options = FixedGridStrategy.OPTION_LOG_ALL
        self.strategy = FixedGridStrategy()
        self.strategy.init_params(
            market_info=MarketTradingPairTuple(*maker_data),
            start_order_spread=start_order_spread,
            n_levels=n_levels,
            grid_price_ceiling=grid_price_ceiling,
            grid_price_floor=grid_price_floor,
            order_amount=order_amount,
            order_refresh_time=order_refresh_time,
            max_order_age=max_order_age,
            order_optimization_enabled=order_optimization_enabled,
            ask_order_optimization_depth=ask_order_optimization_depth,
            bid_order_optimization_depth=bid_order_optimization_depth,
            logging_options=strategy_logging_options,
            take_if_crossed=take_if_crossed,
            order_refresh_tolerance_pct=order_refresh_tolerance_pct,
            hb_app_notification=True,
            should_wait_order_cancel_confirmation=should_wait_order_cancel_confirmation,
        )
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
