from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategyV2,
    ConstantSpreadPricingDelegate,
    ConstantMultipleSpreadPricingDelegate,
    ConstantSizeSizingDelegate,
    StaggeredMultipleSizeSizingDelegate,
    InventorySkewSingleSizeSizingDelegate,
    InventorySkewMultipleSizeSizingDelegate,
    PassThroughFilterDelegate,
    OrderBookAssetPriceDelegate,
    DataFeedAssetPriceDelegate,
    APIAssetPriceDelegate
)
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map
from hummingbot.market.paper_trade import create_paper_trade_market
from hummingbot.market.market_base import MarketBase


def start(self):
    try:
        order_size = pure_market_making_config_map.get("order_amount").value
        cancel_order_wait_time = pure_market_making_config_map.get("cancel_order_wait_time").value
        bid_place_threshold = pure_market_making_config_map.get("bid_place_threshold").value
        ask_place_threshold = pure_market_making_config_map.get("ask_place_threshold").value
        expiration_seconds = pure_market_making_config_map.get("expiration_seconds").value
        mode = pure_market_making_config_map.get("mode").value
        number_of_orders = pure_market_making_config_map.get("number_of_orders").value
        order_start_size = pure_market_making_config_map.get("order_start_size").value
        order_step_size = pure_market_making_config_map.get("order_step_size").value
        order_interval_percent = pure_market_making_config_map.get("order_interval_percent").value
        maker_market = pure_market_making_config_map.get("maker_market").value.lower()
        raw_maker_trading_pair = pure_market_making_config_map.get("maker_market_trading_pair").value
        inventory_skew_enabled = pure_market_making_config_map.get("inventory_skew_enabled").value
        inventory_target_base_percent = pure_market_making_config_map.get("inventory_target_base_percent").value
        filled_order_replenish_wait_time = pure_market_making_config_map.get("filled_order_replenish_wait_time").value
        enable_order_filled_stop_cancellation = pure_market_making_config_map.get(
            "enable_order_filled_stop_cancellation").value
        best_bid_ask_jump_mode = pure_market_making_config_map.get("best_bid_ask_jump_mode").value
        best_bid_ask_jump_orders_depth = pure_market_making_config_map.get("best_bid_ask_jump_orders_depth").value
        add_transaction_costs_to_orders = pure_market_making_config_map.get("add_transaction_costs").value
        external_pricing_source = pure_market_making_config_map.get("external_pricing_source").value
        external_price_source_type = pure_market_making_config_map.get("external_price_source_type").value
        external_price_source_exchange = pure_market_making_config_map.get("external_price_source_exchange").value
        external_price_source_feed_base_asset = pure_market_making_config_map.get(
            "external_price_source_feed_base_asset").value
        external_price_source_feed_quote_asset = pure_market_making_config_map.get(
            "external_price_source_feed_quote_asset").value
        external_price_source_custom_api = pure_market_making_config_map.get("external_price_source_custom_api").value

        pricing_delegate = None
        sizing_delegate = None
        filter_delegate = PassThroughFilterDelegate()

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
            pricing_delegate = ConstantSpreadPricingDelegate(bid_place_threshold,
                                                             ask_place_threshold)
            if inventory_skew_enabled:
                sizing_delegate = InventorySkewSingleSizeSizingDelegate(order_size,
                                                                        inventory_target_base_percent)
            else:
                sizing_delegate = ConstantSizeSizingDelegate(order_size)
        try:
            trading_pair: str = self._convert_to_exchange_trading_pair(maker_market, [raw_maker_trading_pair])[0]
            maker_assets: Tuple[str, str] = self._initialize_market_assets(maker_market, [trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(maker_market, [trading_pair])]
        self._initialize_wallet(token_trading_pairs=list(set(maker_assets)))
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)
        maker_data = [self.markets[maker_market], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]
        asset_price_delegate = None
        if external_pricing_source:
            if external_price_source_type == "exchange":
                asset_trading_pair: str = self._convert_to_exchange_trading_pair(
                    external_price_source_exchange, [raw_maker_trading_pair])[0]
                ext_market = create_paper_trade_market(external_price_source_exchange, [asset_trading_pair])
                self.markets[external_price_source_exchange]: MarketBase = ext_market
                asset_price_delegate = OrderBookAssetPriceDelegate(ext_market, asset_trading_pair)
            elif external_price_source_type == "feed":
                asset_price_delegate = DataFeedAssetPriceDelegate(external_price_source_feed_base_asset,
                                                                  external_price_source_feed_quote_asset)
            elif external_price_source_type == "custom_api":
                asset_price_delegate = APIAssetPriceDelegate(external_price_source_custom_api)
        else:
            asset_price_delegate = None

        strategy_logging_options = PureMarketMakingStrategyV2.OPTION_LOG_ALL

        self.strategy = PureMarketMakingStrategyV2(market_infos=[MarketTradingPairTuple(*maker_data)],
                                                   pricing_delegate=pricing_delegate,
                                                   filter_delegate=filter_delegate,
                                                   sizing_delegate=sizing_delegate,
                                                   filled_order_replenish_wait_time=filled_order_replenish_wait_time,
                                                   enable_order_filled_stop_cancellation=enable_order_filled_stop_cancellation,
                                                   cancel_order_wait_time=cancel_order_wait_time,
                                                   best_bid_ask_jump_mode=best_bid_ask_jump_mode,
                                                   best_bid_ask_jump_orders_depth=best_bid_ask_jump_orders_depth,
                                                   add_transaction_costs_to_orders=add_transaction_costs_to_orders,
                                                   logging_options=strategy_logging_options,
                                                   asset_price_delegate=asset_price_delegate,
                                                   expiration_seconds=expiration_seconds)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
