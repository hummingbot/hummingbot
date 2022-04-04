import pandas as pd
from decimal import Decimal
from typing import (
    List,
    Tuple,
)

from hummingbot import data_path
import os.path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    DailyBetweenTimesModel,
    FromDateToDateModel,
    MultiOrderLevelModel,
    TrackHangingOrdersModel,
)
from hummingbot.strategy.conditional_execution_state import (
    RunAlwaysExecutionState,
    RunInTimeConditionalExecutionState,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.avellaneda_market_making import (
    AvellanedaMarketMakingStrategy,
)


def start(self):
    try:
        c_map = self.strategy_config_map
        order_amount = c_map.order_amount
        order_optimization_enabled = c_map.order_optimization_enabled
        order_refresh_time = c_map.order_refresh_time
        exchange = c_map.exchange
        raw_trading_pair = c_map.market
        max_order_age = c_map.max_order_age
        inventory_target_base_pct = 0 if c_map.inventory_target_base_pct is None else \
            c_map.inventory_target_base_pct / Decimal('100')
        filled_order_delay = c_map.filled_order_delay
        order_refresh_tolerance_pct = c_map.order_refresh_tolerance_pct / Decimal('100')
        if c_map.order_levels_mode.title == MultiOrderLevelModel.Config.title:
            order_levels = c_map.order_levels_mode.order_levels
            level_distances = c_map.order_levels_mode.level_distances
        else:
            order_levels = 1
            level_distances = 0
        order_override = c_map.order_override
        if c_map.hanging_orders_mode.title == TrackHangingOrdersModel.Config.title:
            hanging_orders_enabled = True
            hanging_orders_cancel_pct = c_map.hanging_orders_mode.hanging_orders_cancel_pct / Decimal('100')
        else:
            hanging_orders_enabled = False
            hanging_orders_cancel_pct = Decimal("0")
        add_transaction_costs_to_orders = c_map.add_transaction_costs

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = AvellanedaMarketMakingStrategy.OPTION_LOG_ALL
        risk_factor = c_map.risk_factor
        order_amount_shape_factor = c_map.order_amount_shape_factor

        execution_timeframe = c_map.execution_timeframe_mode.Config.title
        if c_map.execution_timeframe_mode.title == FromDateToDateModel.Config.title:
            start_time = c_map.execution_timeframe_mode.start_datetime
            end_time = c_map.execution_timeframe_mode.end_datetime
            execution_state = RunInTimeConditionalExecutionState(start_timestamp=start_time, end_timestamp=end_time)
        elif c_map.execution_timeframe_mode.title == DailyBetweenTimesModel.Config.title:
            start_time = c_map.execution_timeframe_mode.start_time
            end_time = c_map.execution_timeframe_mode.end_time
            execution_state = RunInTimeConditionalExecutionState(start_timestamp=start_time, end_timestamp=end_time)
        else:
            start_time = None
            end_time = None
            execution_state = RunAlwaysExecutionState()

        min_spread = c_map.min_spread
        volatility_buffer_size = c_map.volatility_buffer_size
        trading_intensity_buffer_size = c_map.trading_intensity_buffer_size
        should_wait_order_cancel_confirmation = c_map.should_wait_order_cancel_confirmation
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
