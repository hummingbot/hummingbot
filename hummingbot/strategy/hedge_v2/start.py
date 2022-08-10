from hummingbot.strategy.hedge_v2.hedge import HedgeStrategy
from hummingbot.strategy.hedge_v2.hedge_v2_config_map import MAX_CONNECTOR, hedge_v2_config_map as c_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    hedge_connector = c_map["hedge_connector"].value.lower()
    hedge_market = c_map["hedge_market"].value
    hedge_leverage = c_map["hedge_leverage"].value
    hedge_interval = c_map["hedge_interval"].value
    hedge_ratio = c_map["hedge_ratio"].value
    min_trade_size = c_map["min_trade_size"].value
    max_order_age = c_map["max_order_age"].value
    slippage = c_map["slippage"].value
    initialize_markets = [(hedge_connector, [hedge_market])]
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

    hedge_market_pair = self.market_trading_pair_tuples[0]
    market_pairs = self.market_trading_pair_tuples[1:]
    self.strategy = HedgeStrategy(
        hedge_market_pair=hedge_market_pair,
        market_pairs = market_pairs,
        hedge_leverage = hedge_leverage,
        hedge_interval = hedge_interval,
        hedge_ratio = hedge_ratio,
        min_trade_size = min_trade_size,
        max_order_age = max_order_age,
        slippage = slippage
    )
