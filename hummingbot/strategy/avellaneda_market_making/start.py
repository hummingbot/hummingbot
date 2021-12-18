import datetime
import pandas as pd
from decimal import Decimal
from typing import (
    List,
    Tuple,
)

from hummingbot import data_path
import os.path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.conditional_execution_state import (
    RunAlwaysExecutionState,
    RunInTimeConditionalExecutionState
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.avellaneda_market_making import (
    AvellanedaMarketMakingStrategy,
)
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import avellaneda_market_making_config_map as c_map


def start(self):
    try:
        order_amount = c_map.get("order_amount").value
        order_optimization_enabled = c_map.get("order_optimization_enabled").value
        order_refresh_time = c_map.get("order_refresh_time").value
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        max_order_age = c_map.get("max_order_age").value
        inventory_target_base_pct = 0 if c_map.get("inventory_target_base_pct").value is None else \
            c_map.get("inventory_target_base_pct").value / Decimal('100')
        filled_order_delay = c_map.get("filled_order_delay").value
        order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal('100')
        order_levels = c_map.get("order_levels").value
        level_distances = c_map.get("level_distances").value
        order_override = c_map.get("order_override").value
        hanging_orders_enabled = c_map.get("hanging_orders_enabled").value

        hanging_orders_cancel_pct = c_map.get("hanging_orders_cancel_pct").value / Decimal('100')
        add_transaction_costs_to_orders = c_map.get("add_transaction_costs").value

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = AvellanedaMarketMakingStrategy.OPTION_LOG_ALL
        risk_factor = c_map.get("risk_factor").value
        order_amount_shape_factor = c_map.get("order_amount_shape_factor").value

        execution_timeframe = c_map.get("execution_timeframe").value

        start_time = c_map.get("start_time").value
        end_time = c_map.get("end_time").value

        if execution_timeframe == "from_date_to_date":
            start_time = datetime.datetime.fromisoformat(start_time)
            end_time = datetime.datetime.fromisoformat(end_time)
            execution_state = RunInTimeConditionalExecutionState(start_timestamp=start_time, end_timestamp=end_time)
        if execution_timeframe == "daily_between_times":
            start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').time()
            end_time = datetime.datetime.strptime(end_time, '%H:%M:%S').time()
            execution_state = RunInTimeConditionalExecutionState(start_timestamp=start_time, end_timestamp=end_time)
        if execution_timeframe == "infinite":
            execution_state = RunAlwaysExecutionState()

        min_spread = c_map.get("min_spread").value
        volatility_buffer_size = c_map.get("volatility_buffer_size").value
        trading_intensity_buffer_size = c_map.get("trading_intensity_buffer_size").value
        should_wait_order_cancel_confirmation = c_map.get("should_wait_order_cancel_confirmation")
        debug_csv_path = os.path.join(data_path(),
                                      HummingbotApplication.main_application().strategy_file_name.rsplit('.', 1)[0] +
                                      f"_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")

        self.strategy = AvellanedaMarketMakingStrategy()
        self.strategy.init_params(
            market_info=MarketTradingPairTuple(*maker_data),
            order_amount=order_amount,
            order_optimization_enabled=order_optimization_enabled,
            inventory_target_base_pct=inventory_target_base_pct,
            order_refresh_time=order_refresh_time,
            max_order_age=max_order_age,
            order_refresh_tolerance_pct=order_refresh_tolerance_pct,
            filled_order_delay=filled_order_delay,
            order_levels=order_levels,
            level_distances=level_distances,
            order_override=order_override,
            hanging_orders_enabled=hanging_orders_enabled,
            hanging_orders_cancel_pct=hanging_orders_cancel_pct,
            add_transaction_costs_to_orders=add_transaction_costs_to_orders,
            logging_options=strategy_logging_options,
            hb_app_notification=True,
            risk_factor=risk_factor,
            order_amount_shape_factor=order_amount_shape_factor,
            execution_timeframe=execution_timeframe,
            execution_state=execution_state,
            start_time=start_time,
            end_time=end_time,
            min_spread=min_spread,
            debug_csv_path=debug_csv_path,
            volatility_buffer_size=volatility_buffer_size,
            trading_intensity_buffer_size=trading_intensity_buffer_size,
            should_wait_order_cancel_confirmation=should_wait_order_cancel_confirmation,
            is_debug=False
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
