from decimal import Decimal

from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map


def start(self):
    connector_1 = amm_arb_config_map.get("connector_1").value.lower()
    market_1 = amm_arb_config_map.get("market_1").value
    connector_2 = amm_arb_config_map.get("connector_2").value.lower()
    market_2 = amm_arb_config_map.get("market_2").value
    order_amount = amm_arb_config_map.get("order_amount").value
    min_profitability = amm_arb_config_map.get("min_profitability").value / Decimal("100")
    market_1_slippage_buffer = amm_arb_config_map.get("market_1_slippage_buffer").value / Decimal("100")
    market_2_slippage_buffer = amm_arb_config_map.get("market_2_slippage_buffer").value / Decimal("100")
    concurrent_orders_submission = amm_arb_config_map.get("concurrent_orders_submission").value
    use_oracle_conversion_rate = amm_arb_config_map.get("use_oracle_conversion_rate").value
    secondary_to_primary_quote_conversion_rate = amm_arb_config_map.get("secondary_to_primary_quote_conversion_rate").value

    self._initialize_markets([(connector_1, [market_1]), (connector_2, [market_2])])
    base_1, quote_1 = market_1.split("-")
    base_2, quote_2 = market_2.split("-")

    market_info_1 = MarketTradingPairTuple(self.markets[connector_1], market_1, base_1, quote_1)
    market_info_2 = MarketTradingPairTuple(self.markets[connector_2], market_2, base_2, quote_2)
    self.market_trading_pair_tuples = [market_info_1, market_info_2]

    if use_oracle_conversion_rate:
        rate_source = RateOracle.get_instance()
    else:
        rate_source = FixedRateSource()
        rate_source.add_rate(f"{quote_2}-{quote_1}", secondary_to_primary_quote_conversion_rate)

    self.strategy = AmmArbStrategy()
    self.strategy.init_params(market_info_1=market_info_1,
                              market_info_2=market_info_2,
                              min_profitability=min_profitability,
                              order_amount=order_amount,
                              market_1_slippage_buffer=market_1_slippage_buffer,
                              market_2_slippage_buffer=market_2_slippage_buffer,
                              concurrent_orders_submission=concurrent_orders_submission,
                              rate_source=rate_source)
