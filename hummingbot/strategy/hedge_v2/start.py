from hummingbot.strategy.hedge_v2.hedge import HedgeStrategy
from hummingbot.strategy.hedge_v2.hedge_v2_config_map import MAX_CONNECTOR, hedge_v2_config_map as c_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from ...core.data_type.common import PositionMode


def start(self):
    hedge_connector = c_map["hedge_connector"].value.lower()
    hedge_markets = c_map["hedge_markets"].value.split(",")
    hedge_leverage = c_map["hedge_leverage"].value
    hedge_interval = c_map["hedge_interval"].value
    hedge_ratio = c_map["hedge_ratio"].value
    hedge_position_mode = PositionMode.HEDGE if c_map["hedge_position_mode"].value.lower() == "hedge" else PositionMode.ONEWAY
    min_trade_size = c_map["min_trade_size"].value
    max_order_age = c_map["max_order_age"].value
    slippage = c_map["slippage"].value
    value_mode = c_map["value_mode"].value
    initialize_markets = [(hedge_connector, hedge_markets)]
    for i in range(MAX_CONNECTOR):
        if not c_map[f"enable_connector_{i}"].value:
            continue
        connector = c_map[f"connector_{i}"].value.lower()
        markets = c_map[f"markets_{i}"].value.split(",")
        initialize_markets.append((connector, markets))
    self._initialize_markets(initialize_markets)
    self.market_trading_pair_tuples = []
    for connector, markets in initialize_markets:
        for market in markets:
            base, quote = market.split("-")
            market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
            self.market_trading_pair_tuples.append(market_info)
    index = len(hedge_markets)
    hedge_market_pair = self.market_trading_pair_tuples[0:index]
    market_pairs = self.market_trading_pair_tuples[index:]
    self.strategy = HedgeStrategy(
        hedge_market_pairs=hedge_market_pair,
        market_pairs = market_pairs,
        hedge_leverage = hedge_leverage,
        hedge_interval = hedge_interval,
        hedge_ratio = hedge_ratio,
        min_trade_size = min_trade_size,
        max_order_age = max_order_age,
        slippage = slippage,
        value_mode = value_mode,
        hedge_position_mode=hedge_position_mode,
    )
