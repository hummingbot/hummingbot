from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategyV2,
    PassThroughFilterDelegate,
    ConstantSpreadPricingDelegate,
    ConstantMultipleSpreadPricingDelegate,
    ConstantSizeSizingDelegate,
    StaggeredMultipleSizeSizingDelegate,
    InventorySkewSingleSizeSizingDelegate,
    InventorySkewMultipleSizeSizingDelegate
)
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map


def start(self):
    try:
        order_size = pure_market_making_config_map.get("order_amount").value
        cancel_order_wait_time = pure_market_making_config_map.get("cancel_order_wait_time").value
        bid_place_threshold = pure_market_making_config_map.get("bid_place_threshold").value
        ask_place_threshold = pure_market_making_config_map.get("ask_place_threshold").value
        mode = pure_market_making_config_map.get("mode").value
        number_of_orders = pure_market_making_config_map.get("number_of_orders").value
        order_start_size = pure_market_making_config_map.get("order_start_size").value
        order_step_size = pure_market_making_config_map.get("order_step_size").value
        order_interval_percent = pure_market_making_config_map.get("order_interval_percent").value
        maker_market = pure_market_making_config_map.get("maker_market").value.lower()
        raw_maker_symbol = pure_market_making_config_map.get("maker_market_symbol").value.upper()
        inventory_skew_enabled = pure_market_making_config_map.get("inventory_skew_enabled").value
        inventory_target_base_percent = pure_market_making_config_map.get("inventory_target_base_percent").value

        filter_delegate = PassThroughFilterDelegate()
        pricing_delegate = None
        sizing_delegate = None
        if mode == "multiple":
            pricing_delegate = ConstantMultipleSpreadPricingDelegate(bid_place_threshold,
                                                                     ask_place_threshold,
                                                                     order_interval_percent,
                                                                     number_of_orders)
            if inventory_skew_enabled:
                sizing_delegate = InventorySkewMultipleSizeSizingDelegate(order_start_size,
                                                                          order_step_size,
                                                                          number_of_orders,
                                                                          inventory_target_base_percent)
            else:
                sizing_delegate = StaggeredMultipleSizeSizingDelegate(order_start_size,
                                                                      order_step_size,
                                                                      number_of_orders)
        else:  # mode == "single"
            pricing_delegate = ConstantSpreadPricingDelegate(bid_place_threshold, ask_place_threshold)
            if inventory_skew_enabled:
                sizing_delegate = InventorySkewSingleSizeSizingDelegate(order_size, inventory_target_base_percent)
            else:
                sizing_delegate = ConstantSizeSizingDelegate(order_size)

        try:
            maker_assets: Tuple[str, str] = self._initialize_market_assets(maker_market, [raw_maker_symbol])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(maker_market, [raw_maker_symbol])]

        self._initialize_wallet(token_symbols=list(set(maker_assets)))
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)

        maker_data = [self.markets[maker_market], raw_maker_symbol] + list(maker_assets)
        self.market_symbol_pairs = [MarketSymbolPair(*maker_data)]

        strategy_logging_options = PureMarketMakingStrategyV2.OPTION_LOG_ALL

        self.strategy = PureMarketMakingStrategyV2(market_infos=[MarketSymbolPair(*maker_data)],
                                                   filter_delegate=filter_delegate,
                                                   pricing_delegate=pricing_delegate,
                                                   sizing_delegate=sizing_delegate,
                                                   cancel_order_wait_time=cancel_order_wait_time,
                                                   logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
