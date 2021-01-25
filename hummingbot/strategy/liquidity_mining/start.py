from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.liquidity_mining.liquidity_mining import LiquidityMiningStrategy
from hummingbot.strategy.liquidity_mining.liquidity_mining_config_map import liquidity_mining_config_map as c_map


def start(self):
    exchange = c_map.get("exchange").value.lower()
    markets = list(c_map.get("markets").value.split(","))
    token = c_map.get("token").value
    order_size = c_map.get("order_size").value
    spread = c_map.get("spread").value / Decimal("100")
    base_targets = c_map.get("target_base_pct").value
    base_targets = {k: Decimal(str(v)) / Decimal("100") for k, v in base_targets.items()}
    order_refresh_time = c_map.get("order_refresh_time").value
    order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal("100")

    self._initialize_markets([(exchange, markets)])
    exchange = self.markets[exchange]
    market_infos = {}
    for market in markets:
        base, quote = market.split("-")
        market_infos[market] = MarketTradingPairTuple(exchange, market, base, quote)
    self.strategy = LiquidityMiningStrategy(
        exchange=exchange,
        market_infos=market_infos,
        token=token,
        order_size=order_size,
        spread=spread,
        target_base_pcts=base_targets,
        order_refresh_time=order_refresh_time,
        order_refresh_tolerance_pct=order_refresh_tolerance_pct
    )
