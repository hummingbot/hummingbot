from hummingbot.strategy.cross_exchange_arb_logger import CrossExchangeArbLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self, exchange_1, market_1, exchange_2, market_2):
    self._initialize_markets(
        [
            (exchange_1, [market_1]),
            (exchange_2, [market_2])
        ]
    )
    base_1, quote_1 = market_1.split("-")
    base_2, quote_2 = market_1.split("-")
    market_1_info = MarketTradingPairTuple(self.markets[exchange_1], market_1, base_1, quote_1)
    market_2_info = MarketTradingPairTuple(self.markets[exchange_2], market_2, base_2, quote_2)
    self.market_trading_pair_tuples = [market_1_info, market_2_info]

    self.strategy = CrossExchangeArbLogger(market_1_info, market_2_info)
