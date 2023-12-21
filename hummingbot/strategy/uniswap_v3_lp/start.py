from decimal import Decimal

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp_config_map import uniswap_v3_lp_config_map as c_map


def start(self):
    connector = c_map.get("connector").value
    pair = c_map.get("market").value
    fee_tier = c_map.get("fee_tier").value
    price_spread = c_map.get("price_spread").value / Decimal("100")
    min_amount = c_map.get("min_amount").value
    max_amount = c_map.get("max_amount").value
    min_profitability = c_map.get("min_profitability").value

    self._initialize_markets([(connector, [pair])])
    base, quote = pair.split("-")

    market_info = MarketTradingPairTuple(self.markets[connector], pair, base, quote)
    self.market_trading_pair_tuples = [market_info]
    self.strategy = UniswapV3LpStrategy(market_info,
                                        fee_tier,
                                        price_spread,
                                        min_amount,
                                        max_amount,
                                        min_profitability)
