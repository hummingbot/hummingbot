from decimal import Decimal
from typing import List, Optional, Tuple

from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.api_asset_price_delegate import APIAssetPriceDelegate
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate
from hummingbot.strategy.pure_market_making import InventoryCostPriceDelegate, PureMarketMakingStrategy
from hummingbot.strategy.pure_market_making.moving_price_band import MovingPriceBand
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map as c_map


def start(self):
    def convert_decimal_string_to_list(string: Optional[str], divisor: Decimal = Decimal("1")) -> List[Decimal]:
        '''convert order level spread string into a list of decimal divided by divisor '''
        if string is None:
            return []
        string_list = list(string.split(","))
        return [Decimal(v) / divisor for v in string_list]

    try:
        order_amount = c_map.get("order_amount").value
        order_refresh_time = c_map.get("order_refresh_time").value
        max_order_age = c_map.get("max_order_age").value
        bid_spread = c_map.get("bid_spread").value / Decimal('100')
        ask_spread = c_map.get("ask_spread").value / Decimal('100')
        minimum_spread = c_map.get("minimum_spread").value / Decimal('100')
        price_ceiling = c_map.get("price_ceiling").value
        price_floor = c_map.get("price_floor").value
        ping_pong_enabled = c_map.get("ping_pong_enabled").value
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
        price_source = c_map.get("price_source").value
        price_type = c_map.get("price_type").value
        price_source_exchange = c_map.get("price_source_exchange").value
        price_source_market = c_map.get("price_source_market").value
        price_source_custom_api = c_map.get("price_source_custom_api").value
        custom_api_update_interval = c_map.get("custom_api_update_interval").value
        order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal('100')
        order_override = c_map.get("order_override").value
        split_order_levels_enabled = c_map.get("split_order_levels_enabled").value
        moving_price_band = MovingPriceBand(
            enabled=c_map.get("moving_price_band_enabled").value,
            price_floor_pct=c_map.get("price_floor_pct").value,
            price_ceiling_pct=c_map.get("price_ceiling_pct").value,
            price_band_refresh_time=c_map.get("price_band_refresh_time").value
        )
        bid_order_level_spreads = convert_decimal_string_to_list(
            c_map.get("bid_order_level_spreads").value)
        ask_order_level_spreads = convert_decimal_string_to_list(
            c_map.get("ask_order_level_spreads").value)
        bid_order_level_amounts = convert_decimal_string_to_list(
            c_map.get("bid_order_level_amounts").value)
        ask_order_level_amounts = convert_decimal_string_to_list(
            c_map.get("ask_order_level_amounts").value)
        if split_order_levels_enabled:
            buy_list = [['buy', spread, amount] for spread, amount in zip(bid_order_level_spreads, bid_order_level_amounts)]
            sell_list = [['sell', spread, amount] for spread, amount in zip(ask_order_level_spreads, ask_order_level_amounts)]
            both_list = buy_list + sell_list
            order_override = {
                f'split_level_{i}': order for i, order in enumerate(both_list)
            }
        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = trading_pair.split("-")
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self.initialize_markets(market_names)
        maker_data = [self.connector_manager.connectors[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        asset_price_delegate = None
        if price_source == "external_market":
            asset_trading_pair: str = price_source_market
            ext_market = create_paper_trade_market(price_source_exchange, self.client_config_map, [asset_trading_pair])
            self.connector_manager.connectors[price_source_exchange]: ExchangeBase = ext_market
            asset_price_delegate = OrderBookAssetPriceDelegate(ext_market, asset_trading_pair)
        elif price_source == "custom_api":
            asset_price_delegate = APIAssetPriceDelegate(self.markets[exchange], price_source_custom_api,
                                                         custom_api_update_interval)
        inventory_cost_price_delegate = None
        if price_type == "inventory_cost":
            db = self.trade_fill_db
            inventory_cost_price_delegate = InventoryCostPriceDelegate(db, trading_pair)
        take_if_crossed = c_map.get("take_if_crossed").value

        should_wait_order_cancel_confirmation = c_map.get("should_wait_order_cancel_confirmation")

        strategy_logging_options = PureMarketMakingStrategy.OPTION_LOG_ALL
        self.strategy = PureMarketMakingStrategy()
        self.strategy.init_params(
            market_info=MarketTradingPairTuple(*maker_data),
            bid_spread=bid_spread,
            ask_spread=ask_spread,
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
            max_order_age=max_order_age,
            order_optimization_enabled=order_optimization_enabled,
            ask_order_optimization_depth=ask_order_optimization_depth,
            bid_order_optimization_depth=bid_order_optimization_depth,
            add_transaction_costs_to_orders=add_transaction_costs_to_orders,
            logging_options=strategy_logging_options,
            asset_price_delegate=asset_price_delegate,
            inventory_cost_price_delegate=inventory_cost_price_delegate,
            price_type=price_type,
            take_if_crossed=take_if_crossed,
            price_ceiling=price_ceiling,
            price_floor=price_floor,
            ping_pong_enabled=ping_pong_enabled,
            hanging_orders_cancel_pct=hanging_orders_cancel_pct,
            order_refresh_tolerance_pct=order_refresh_tolerance_pct,
            minimum_spread=minimum_spread,
            hb_app_notification=True,
            order_override={} if order_override is None else order_override,
            split_order_levels_enabled=split_order_levels_enabled,
            bid_order_level_spreads=bid_order_level_spreads,
            ask_order_level_spreads=ask_order_level_spreads,
            should_wait_order_cancel_confirmation=should_wait_order_cancel_confirmation,
            moving_price_band=moving_price_band
        )
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
