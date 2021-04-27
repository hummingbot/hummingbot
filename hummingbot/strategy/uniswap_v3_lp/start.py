from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp import uniswap_v3_lp_config_map as c_map
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy


def start(self):
    pair = c_map.get("market").value
    range_order_quote_amount = c_map.get("range_order_quote_amount").value
    range_order_spread = c_map.get("range_order_spread").value / Decimal("100")

    self._initialize_markets([("uniswap_v3", [pair])])
    base, quote = pair.split("-")
    self.assets = {base, quote}

    market_info = MarketTradingPairTuple(self.markets["uniswap_v3"], pair, base, quote)
    self.strategy = UniswapV3LpStrategy(market_info, range_order_quote_amount, range_order_spread)
