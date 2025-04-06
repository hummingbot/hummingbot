from decimal import Decimal
from typing import List, Tuple

from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.api_asset_price_delegate import APIAssetPriceDelegate
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate
from hummingbot.strategy.perpetual_market_making import PerpetualMarketMakingStrategy
from hummingbot.strategy.perpetual_market_making.perpetual_market_making_config_map import (
    perpetual_market_making_config_map as c_map,
)


def start(self):
    try:
        leverage = c_map.get("leverage").value
        position_mode = c_map.get("position_mode").value
        order_amount = c_map.get("order_amount").value
        order_refresh_time = c_map.get("order_refresh_time").value
        bid_spread = c_map.get("bid_spread").value / Decimal('100')
        ask_spread = c_map.get("ask_spread").value / Decimal('100')
        long_profit_taking_spread = c_map.get("long_profit_taking_spread").value / Decimal('100')
        short_profit_taking_spread = c_map.get("short_profit_taking_spread").value / Decimal('100')
        stop_loss_spread = c_map.get("stop_loss_spread").value / Decimal('100')
        time_between_stop_loss_orders = c_map.get("time_between_stop_loss_orders").value
        stop_loss_slippage_buffer = c_map.get("stop_loss_slippage_buffer").value / Decimal('100')
        minimum_spread = c_map.get("minimum_spread").value / Decimal('100')
        price_ceiling = c_map.get("price_ceiling").value
        price_floor = c_map.get("price_floor").value
        order_levels = c_map.get("order_levels").value
        order_level_amount = c_map.get("order_level_amount").value
        order_level_spread = c_map.get("order_level_spread").value / Decimal('100')
        exchange = c_map.get("derivative").value.lower()
        raw_trading_pair = c_map.get("market").value
        filled_order_delay = c_map.get("filled_order_delay").value
        order_optimization_enabled = c_map.get("order_optimization_enabled").value
        ask_order_optimization_depth = c_map.get("ask_order_optimization_depth").value
        bid_order_optimization_depth = c_map.get("bid_order_optimization_depth").value
        price_source = c_map.get("price_source").value
        price_type = c_map.get("price_type").value
        price_source_exchange = c_map.get("price_source_derivative").value
        price_source_market = c_map.get("price_source_market").value
        price_source_custom_api = c_map.get("price_source_custom_api").value
        custom_api_update_interval = c_map.get("custom_api_update_interval").value
        order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal('100')
        order_override = c_map.get("order_override").value

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]
        asset_price_delegate = None
        if price_source == "external_market":
            asset_trading_pair: str = price_source_market
            ext_market = create_paper_trade_market(
                price_source_exchange, self.client_config_map, [asset_trading_pair]
            )
            self.markets[price_source_exchange]: ExchangeBase = ext_market
            asset_price_delegate = OrderBookAssetPriceDelegate(ext_market, asset_trading_pair)
        elif price_source == "custom_api":
            ext_market = create_paper_trade_market(
                exchange, self.client_config_map, [raw_trading_pair]
            )
            asset_price_delegate = APIAssetPriceDelegate(ext_market, price_source_custom_api,
                                                         custom_api_update_interval)

        strategy_logging_options = PerpetualMarketMakingStrategy.OPTION_LOG_ALL

        self.strategy = PerpetualMarketMakingStrategy()
        self.strategy.init_params(
            market_info=MarketTradingPairTuple(*maker_data),
            leverage=leverage,
            position_mode=position_mode,
            bid_spread=bid_spread,
            ask_spread=ask_spread,
            order_amount=order_amount,
            long_profit_taking_spread=long_profit_taking_spread,
            short_profit_taking_spread=short_profit_taking_spread,
            stop_loss_spread=stop_loss_spread,
            time_between_stop_loss_orders=time_between_stop_loss_orders,
            stop_loss_slippage_buffer=stop_loss_slippage_buffer,
            order_levels=order_levels,
            order_level_spread=order_level_spread,
            order_level_amount=order_level_amount,
            order_refresh_time=order_refresh_time,
            order_refresh_tolerance_pct=order_refresh_tolerance_pct,
            filled_order_delay=filled_order_delay,
            order_optimization_enabled=order_optimization_enabled,
            ask_order_optimization_depth=ask_order_optimization_depth,
            bid_order_optimization_depth=bid_order_optimization_depth,
            asset_price_delegate=asset_price_delegate,
            price_type=price_type,
            price_ceiling=price_ceiling,
            price_floor=price_floor,
            logging_options=strategy_logging_options,
            minimum_spread=minimum_spread,
            hb_app_notification=True,
            order_override=order_override,
        )
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
