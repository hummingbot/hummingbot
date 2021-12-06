from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp_config_map import uniswap_v3_lp_config_map as c_map
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy


def start(self):
    pair = c_map.get("market").value
    fee_tier = c_map.get("fee_tier").value
    use_volatility = c_map.get("use_volatility").value
    volatility_period = c_map.get("volatility_period").value
    volatility_factor = c_map.get("volatility_factor").value
    buy_spread = c_map.get("buy_spread").value / Decimal("100")
    sell_spread = c_map.get("sell_spread").value / Decimal("100")
    base_token_amount = c_map.get("base_token_amount").value
    quote_token_amount = c_map.get("quote_token_amount").value
    min_profitability = c_map.get("min_profitability").value / Decimal("100")

    self._initialize_markets([("uniswap_v3", [pair])])
    base, quote = pair.split("-")

    market_info = MarketTradingPairTuple(self.markets["uniswap_v3"], pair, base, quote)
    self.market_trading_pair_tuples = [market_info]
    self.strategy = UniswapV3LpStrategy(market_info,
                                        fee_tier,
                                        use_volatility,
                                        volatility_period,
                                        volatility_factor,
                                        buy_spread,
                                        sell_spread,
                                        base_token_amount,
                                        quote_token_amount,
                                        min_profitability)
