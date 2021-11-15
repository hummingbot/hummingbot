from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.dev_5_vwap import Dev5TwapTradeStrategy
from hummingbot.strategy.dev_5_vwap.dev_5_vwap_config_map import dev_5_vwap_config_map


def start(self):
    try:
        order_amount = dev_5_vwap_config_map.get("order_amount").value
        order_type = dev_5_vwap_config_map.get("order_type").value
        is_buy = dev_5_vwap_config_map.get("is_buy").value
        time_delay = dev_5_vwap_config_map.get("time_delay").value
        is_vwap = dev_5_vwap_config_map.get("is_vwap").value
        num_individual_orders = dev_5_vwap_config_map.get("num_individual_orders").value
        percent_slippage = dev_5_vwap_config_map.get("percent_slippage").value
        order_percent_of_volume = dev_5_vwap_config_map.get("order_percent_of_volume").value
        exchange = dev_5_vwap_config_map.get("exchange").value.lower()
        raw_market_symbol = dev_5_vwap_config_map.get("market").value
        order_price = None
        cancel_order_wait_time = None

        if order_type == "limit":
            order_price = dev_5_vwap_config_map.get("order_price").value
            cancel_order_wait_time = dev_5_vwap_config_map.get("cancel_order_wait_time").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(exchange, [raw_market_symbol])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(exchange, [raw_market_symbol])]

        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], raw_market_symbol] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        self.strategy = Dev5TwapTradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                              order_type=order_type,
                                              order_price=order_price,
                                              cancel_order_wait_time=cancel_order_wait_time,
                                              is_buy=is_buy,
                                              time_delay=time_delay,
                                              is_vwap=is_vwap,
                                              num_individual_orders=num_individual_orders,
                                              percent_slippage=percent_slippage,
                                              order_percent_of_volume=order_percent_of_volume,
                                              order_amount=order_amount)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
