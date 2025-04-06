from hummingbot.strategy.hedge.hedge import HedgeStrategy
from hummingbot.strategy.hedge.hedge_config_map_pydantic import MAX_CONNECTOR, HedgeConfigMap
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    c_map: HedgeConfigMap = self.strategy_config_map
    hedge_connector = c_map.hedge_connector.lower()
    hedge_markets = c_map.hedge_markets
    hedge_offsets = c_map.hedge_offsets
    offsets_dict = {hedge_connector: hedge_offsets}
    initialize_markets = [(hedge_connector, hedge_markets)]
    for i in range(MAX_CONNECTOR):
        connector_config = getattr(c_map, f"connector_{i}")
        connector = connector_config.connector
        if not connector:
            continue
        connector = connector.lower()
        markets = connector_config.markets
        offsets_dict[connector] = connector_config.offsets
        initialize_markets.append((connector, markets))
    self._initialize_markets(initialize_markets)
    self.market_trading_pair_tuples = []
    offsets_market_dict = {}
    for connector, markets in initialize_markets:
        offsets = offsets_dict[connector]
        for market, offset in zip(markets, offsets):
            base, quote = market.split("-")
            market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
            self.market_trading_pair_tuples.append(market_info)
            offsets_market_dict[market_info] = offset
    index = len(hedge_markets)
    hedge_market_pairs = self.market_trading_pair_tuples[0:index]
    market_pairs = self.market_trading_pair_tuples[index:]
    self.strategy = HedgeStrategy(
        config_map=c_map, hedge_market_pairs=hedge_market_pairs, market_pairs=market_pairs, offsets=offsets_market_dict
    )
