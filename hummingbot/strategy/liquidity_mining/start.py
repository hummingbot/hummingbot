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
    target_base_pct = c_map.get("target_base_pct").value / Decimal("100")
    order_refresh_time = c_map.get("order_refresh_time").value
    order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal("100")
    inventory_range_multiplier = c_map.get("inventory_range_multiplier").value
    volatility_interval = c_map.get("volatility_interval").value
    avg_volatility_period = c_map.get("avg_volatility_period").value
    volatility_to_spread_multiplier = c_map.get("volatility_to_spread_multiplier").value

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
        target_base_pct=target_base_pct,
        order_refresh_time=order_refresh_time,
        order_refresh_tolerance_pct=order_refresh_tolerance_pct,
        inventory_range_multiplier=inventory_range_multiplier,
        volatility_interval=volatility_interval,
        avg_volatility_period=avg_volatility_period,
        volatility_to_spread_multiplier=volatility_to_spread_multiplier,
        hb_app_notification=True
    )
