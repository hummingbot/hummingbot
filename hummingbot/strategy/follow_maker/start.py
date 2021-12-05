from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.follow_maker import FollowMaker
from hummingbot.strategy.follow_maker.follow_maker_config_map import follow_order_config_map as c_map
from .follow_maker import FollowMaker

def start(self):
    connector = c_map.get("connector").value.lower()
    market = c_map.get("market").value

    self._initialize_markets([(connector, [market])])
    base, quote = market.split("-")
    market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
    self.market_trading_pair_tuples = [market_info]

    self.strategy = FollowMaker(market_info)
