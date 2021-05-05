from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp_config_map import uniswap_v3_lp_config_map as c_map
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy


def start(self):
    pair = c_map.get("market").value
    fee_tier = c_map.get("fee_tier").value
    buy_position_spread = c_map.get("buy_position_spread").value / Decimal("100")
    sell_position_spread = c_map.get("sell_position_spread").value / Decimal("100")
    buy_position_price_spread = c_map.get("buy_position_price_spread").value / Decimal("100")
    sell_position_price_spread = c_map.get("sell_position_price_spread").value / Decimal("100")
    token_amount = c_map.get("token_amount").value

    self._initialize_markets([("uniswap_v3", [pair])])
    base, quote = pair.split("-")
    self.assets = set([base, quote])

    market_info = MarketTradingPairTuple(self.markets["uniswap_v3"], pair, base, quote)
    self.market_trading_pair_tuples = [market_info]
    self.strategy = UniswapV3LpStrategy(market_info,
                                        fee_tier,
                                        buy_position_spread,
                                        sell_position_spread,
                                        buy_position_price_spread,
                                        sell_position_price_spread,
                                        token_amount)
