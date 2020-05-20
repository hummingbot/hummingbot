from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.dev_2_perform_trade import PerformTradeStrategy
from hummingbot.strategy.dev_2_perform_trade.dev_2_perform_trade_config_map import dev_2_perform_trade_config_map


def start(self):
    try:
        order_amount = dev_2_perform_trade_config_map.get("order_amount").value
        order_type = dev_2_perform_trade_config_map.get("order_type").value
        is_buy = dev_2_perform_trade_config_map.get("is_buy").value
        market = dev_2_perform_trade_config_map.get("market").value.lower()
        raw_market_trading_pair = dev_2_perform_trade_config_map.get("market_trading_pair_tuple").value
        order_price = None

        if order_type == "limit":
            order_price = dev_2_perform_trade_config_map.get("order_price").value

        try:
            trading_pair: str = self._convert_to_exchange_trading_pair(market, [raw_market_trading_pair])[0]
            assets: Tuple[str, str] = self._initialize_market_assets(market, [trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [trading_pair])]

        self._initialize_wallet(token_trading_pairs=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        strategy_logging_options = PerformTradeStrategy.OPTION_LOG_ALL

        self.strategy = PerformTradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                             order_type=order_type,
                                             order_price=order_price,
                                             is_buy=is_buy,
                                             order_amount=order_amount,
                                             logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
