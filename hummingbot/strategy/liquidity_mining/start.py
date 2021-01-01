from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.liquidity_mining.liquidity_mining import LiquidityMiningStrategy
from hummingbot.strategy.liquidity_mining.liquidity_mining_config_map import liquidity_mining_config_map as c_map


def start(self):
    exchange = c_map.get("exchange").value.lower()
    markets_text = c_map.get("markets").value
    initial_spread = c_map.get("initial_spread").value / Decimal("100")
    order_refresh_time = c_map.get("order_refresh_time").value
    order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal("100")
    markets = list(markets_text.split(","))

    self._initialize_markets([(exchange, markets)])
    exchange = self.markets[exchange]
    market_infos = {}
    for market in markets:
        base, quote = market.split("-")
        market_infos[market] = MarketTradingPairTuple(exchange, market, base, quote)
    self.strategy = LiquidityMiningStrategy(exchange=exchange,
                                            market_infos=market_infos,
                                            initial_spread=initial_spread,
                                            order_refresh_time=order_refresh_time,
                                            order_refresh_tolerance_pct=order_refresh_tolerance_pct)
