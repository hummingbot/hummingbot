from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp_config_map import uniswap_v3_lp_config_map as c_map
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy


def start(self):
    pair = c_map.get("market").value
    upper_price_bound = c_map.get("upper_price_bound").value
    lower_price_bound = c_map.get("lower_price_bound").value
    boundaries_margin = c_map.get("boundaries_margin").value / Decimal("100")
    token = c_map.get("token").value
    token_amount = c_map.get("token_amount").value

    self._initialize_markets([("uniswap_v3", [pair])])
    base, quote = pair.split("-")
    self.assets = {base, quote}

    market_info = MarketTradingPairTuple(self.markets["uniswap_v3"], pair, base, quote)
    self.strategy = UniswapV3LpStrategy(market_info, upper_price_bound, lower_price_bound, boundaries_margin,
                                        token, token_amount)
