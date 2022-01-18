from typing import (
    List,
    Tuple,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.dev_simple_trade import SimpleTradeStrategy
from hummingbot.strategy.dev_simple_trade.dev_simple_trade_config_map import dev_simple_trade_config_map


def start(self):
    try:
        order_amount = dev_simple_trade_config_map.get("order_amount").value
        order_type = dev_simple_trade_config_map.get("order_type").value
        is_buy = dev_simple_trade_config_map.get("is_buy").value
        time_delay = dev_simple_trade_config_map.get("time_delay").value
        market = dev_simple_trade_config_map.get("market").value.lower()
        raw_market_trading_pair = dev_simple_trade_config_map.get("market_trading_pair_tuple").value
        order_price = None
        cancel_order_wait_time = None

        if order_type == "limit":
            order_price = dev_simple_trade_config_map.get("order_price").value
            cancel_order_wait_time = dev_simple_trade_config_map.get("cancel_order_wait_time").value

        try:
            trading_pair: str = raw_market_trading_pair
            assets: Tuple[str, str] = self._initialize_market_assets(market, [trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [trading_pair])]

        self._initialize_markets(market_names)

        maker_data = [self.markets[market], trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = SimpleTradeStrategy.OPTION_LOG_ALL

        self.strategy = SimpleTradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                            order_type=order_type,
                                            order_price=order_price if order_price else None,
                                            cancel_order_wait_time=cancel_order_wait_time,
                                            is_buy=is_buy,
                                            time_delay=time_delay,
                                            order_amount=order_amount,
                                            logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
