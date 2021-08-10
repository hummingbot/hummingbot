from typing import (
    List,
    Tuple,
)

from hummingbot import data_path
import os.path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.hanging_orders_tracker import HangingOrdersAggregationType
from hummingbot.strategy.avellaneda_market_making import (
    AvellanedaMarketMakingStrategy,
)
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import avellaneda_market_making_config_map as c_map
from decimal import Decimal
import pandas as pd


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
        order_override = c_map.get("order_override").value
        hanging_orders_enabled = c_map.get("hanging_orders_enabled").value
        hanging_orders_aggregation_type = HangingOrdersAggregationType.NO_AGGREGATION
        # if hanging_orders_enabled:
        #     hanging_orders_aggregation_type = getattr(HangingOrdersAggregationType,
        #                                               c_map.get("hanging_orders_aggregation_type").value.upper())
        # else:
        #     hanging_orders_aggregation_type = HangingOrdersAggregationType.NO_AGGREGATION
        hanging_orders_cancel_pct = c_map.get("hanging_orders_cancel_pct").value / Decimal('100')
        add_transaction_costs_to_orders = c_map.get("add_transaction_costs").value

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_wallet(token_trading_pairs=list(set(maker_assets)))
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = AvellanedaMarketMakingStrategy.OPTION_LOG_ALL
        parameters_based_on_spread = c_map.get("parameters_based_on_spread").value
        if parameters_based_on_spread:
            risk_factor = order_book_depth_factor = order_amount_shape_factor = None
            min_spread = c_map.get("min_spread").value / Decimal(100)
            max_spread = c_map.get("max_spread").value / Decimal(100)
            vol_to_spread_multiplier = c_map.get("vol_to_spread_multiplier").value
            volatility_sensibility = c_map.get("volatility_sensibility").value / Decimal('100')
            inventory_risk_aversion = c_map.get("inventory_risk_aversion").value
        else:
            min_spread = max_spread = vol_to_spread_multiplier = inventory_risk_aversion = volatility_sensibility = None
            order_book_depth_factor = c_map.get("order_book_depth_factor").value
            risk_factor = c_map.get("risk_factor").value
            order_amount_shape_factor = c_map.get("order_amount_shape_factor").value
        closing_time = c_map.get("closing_time").value * Decimal(3600 * 24 * 1e3)
        volatility_buffer_size = c_map.get("volatility_buffer_size").value
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
            order_override=order_override,
            hanging_orders_enabled=hanging_orders_enabled,
            hanging_orders_aggregation_type=hanging_orders_aggregation_type,
            hanging_orders_cancel_pct=hanging_orders_cancel_pct,
            add_transaction_costs_to_orders=add_transaction_costs_to_orders,
            logging_options=strategy_logging_options,
            hb_app_notification=True,
            parameters_based_on_spread=parameters_based_on_spread,
            min_spread=min_spread,
            max_spread=max_spread,
            vol_to_spread_multiplier=vol_to_spread_multiplier,
            volatility_sensibility=volatility_sensibility,
            inventory_risk_aversion=inventory_risk_aversion,
            order_book_depth_factor=order_book_depth_factor,
            risk_factor=risk_factor,
            order_amount_shape_factor=order_amount_shape_factor,
            closing_time=closing_time,
            debug_csv_path=debug_csv_path,
            volatility_buffer_size=volatility_buffer_size,
            is_debug=False
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
