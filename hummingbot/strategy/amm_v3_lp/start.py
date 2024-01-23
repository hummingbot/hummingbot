from decimal import Decimal

from hummingbot.strategy.amm_v3_lp.amm_v3_lp import AmmV3LpStrategy
from hummingbot.strategy.amm_v3_lp.amm_v3_lp_config_map import amm_v3_lp_config_map as c_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    connector = c_map.get("connector").value
    pair = c_map.get("market").value
    fee_tier = c_map.get("fee_tier").value
    price_spread = c_map.get("price_spread").value / Decimal("100")
    buffer_spread = c_map.get("buffer_spread").value / Decimal("100")
    min_amount = c_map.get("min_amount").value
    max_amount = c_map.get("max_amount").value
    min_profitability = c_map.get("min_profitability").value
    status_report_interval = c_map.get("status_report_interval").value

    self._initialize_markets([(connector, [pair])])
    base, quote = pair.split("-")

    market_info = MarketTradingPairTuple(self.markets[connector], pair, base, quote)
    self.market_trading_pair_tuples = [market_info]
    self.strategy = AmmV3LpStrategy(market_info,
                                    fee_tier,
                                    price_spread,
                                    buffer_spread,
                                    min_amount,
                                    max_amount,
                                    min_profitability,
                                    status_report_interval)
