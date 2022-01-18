from typing import (
    List,
    Tuple,
)

from hummingbot import data_path
import os.path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.aroon_oscillator import (
    AroonOscillatorStrategy,
)
from hummingbot.strategy.aroon_oscillator.aroon_oscillator_config_map import aroon_oscillator_config_map as c_map
from decimal import Decimal
import pandas as pd


def start(self):
    try:
        order_amount = c_map.get("order_amount").value
        order_refresh_time = c_map.get("order_refresh_time").value
        max_order_age = c_map.get("max_order_age").value
        minimum_spread = c_map.get("minimum_spread").value / Decimal('100')
        maximum_spread = c_map.get("maximum_spread").value / Decimal('100')
        period_length = c_map.get("period_length").value
        period_duration = c_map.get("period_duration").value
        minimum_periods = c_map.get("minimum_periods").value
        aroon_osc_strength_factor = c_map.get("aroon_osc_strength_factor").value
        price_ceiling = c_map.get("price_ceiling").value
        price_floor = c_map.get("price_floor").value
        order_levels = c_map.get("order_levels").value
        order_level_amount = c_map.get("order_level_amount").value
        order_level_spread = c_map.get("order_level_spread").value / Decimal('100')
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        inventory_skew_enabled = c_map.get("inventory_skew_enabled").value
        inventory_target_base_pct = 0 if c_map.get("inventory_target_base_pct").value is None else \
            c_map.get("inventory_target_base_pct").value / Decimal('100')
        inventory_range_multiplier = c_map.get("inventory_range_multiplier").value
        filled_order_delay = c_map.get("filled_order_delay").value
        hanging_orders_enabled = c_map.get("hanging_orders_enabled").value
        hanging_orders_cancel_pct = c_map.get("hanging_orders_cancel_pct").value / Decimal('100')
        order_optimization_enabled = c_map.get("order_optimization_enabled").value
        ask_order_optimization_depth = c_map.get("ask_order_optimization_depth").value
        bid_order_optimization_depth = c_map.get("bid_order_optimization_depth").value
        add_transaction_costs_to_orders = c_map.get("add_transaction_costs").value
        price_type = c_map.get("price_type").value
        order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal('100')
        order_override = c_map.get("order_override").value
        cancel_order_spread_threshold = c_map.get("cancel_order_spread_threshold").value / Decimal('100')

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]
        take_if_crossed = c_map.get("take_if_crossed").value

        debug_csv_path = os.path.join(data_path(),
                                      HummingbotApplication.main_application().strategy_file_name.rsplit('.', 1)[0] +
                                      f"_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")

        strategy_logging_options = AroonOscillatorStrategy.OPTION_LOG_ALL

        self.strategy = AroonOscillatorStrategy(
            market_info=MarketTradingPairTuple(*maker_data),
            minimum_spread=minimum_spread,
            maximum_spread=maximum_spread,
            period_length=period_length,
            period_duration=period_duration,
            minimum_periods=minimum_periods,
            aroon_osc_strength_factor=aroon_osc_strength_factor,
            order_levels=order_levels,
            order_amount=order_amount,
            order_level_spread=order_level_spread,
            order_level_amount=order_level_amount,
            inventory_skew_enabled=inventory_skew_enabled,
            inventory_target_base_pct=inventory_target_base_pct,
            inventory_range_multiplier=inventory_range_multiplier,
            filled_order_delay=filled_order_delay,
            hanging_orders_enabled=hanging_orders_enabled,
            order_refresh_time=order_refresh_time,
            max_order_age = max_order_age,
            order_optimization_enabled=order_optimization_enabled,
            ask_order_optimization_depth=ask_order_optimization_depth,
            bid_order_optimization_depth=bid_order_optimization_depth,
            add_transaction_costs_to_orders=add_transaction_costs_to_orders,
            logging_options=strategy_logging_options,
            price_type=price_type,
            take_if_crossed=take_if_crossed,
            price_ceiling=price_ceiling,
            price_floor=price_floor,
            hanging_orders_cancel_pct=hanging_orders_cancel_pct,
            order_refresh_tolerance_pct=order_refresh_tolerance_pct,
            cancel_order_spread_threshold=cancel_order_spread_threshold,
            hb_app_notification=True,
            order_override={} if order_override is None else order_override,
            debug_csv_path=debug_csv_path,
            is_debug=True
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
