from decimal import Decimal

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


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
    rate_oracle_enabled = amm_arb_config_map.get("rate_oracle_enabled").value
    quote_conversion_rate = amm_arb_config_map.get("quote_conversion_rate").value
    gas_token = amm_arb_config_map.get("gas_token").value
    gas_price = amm_arb_config_map.get("gas_price").value

    self.initialize_markets([(connector_1, [market_1]), (connector_2, [market_2])])
    base_1, quote_1 = market_1.split("-")
    base_2, quote_2 = market_2.split("-")

    is_connector_1_gateway = connector_1 in sorted(AllConnectorSettings.get_gateway_amm_connector_names())

    is_connector_2_gateway = connector_2 in sorted(AllConnectorSettings.get_gateway_amm_connector_names())

    market_info_1 = MarketTradingPairTuple(
        self.markets[connector_1], market_1 if not is_connector_1_gateway else market_1, base_1, quote_1
    )
    market_info_2 = MarketTradingPairTuple(
        self.markets[connector_2], market_2 if not is_connector_2_gateway else market_2, base_2, quote_2
    )
    self.market_trading_pair_tuples = [market_info_1, market_info_2]

    if rate_oracle_enabled:
        rate_source = RateOracle.get_instance()
    else:
        rate_source = FixedRateSource()
        rate_source.add_rate(f"{quote_2}-{quote_1}", Decimal(str(quote_conversion_rate)))   # reverse rate is already handled in FixedRateSource find_rate method.
        rate_source.add_rate(f"{quote_1}-{quote_2}", Decimal(str(1 / quote_conversion_rate)))   # reverse rate is already handled in FixedRateSource find_rate method.

        if gas_price:
            rate_source.add_rate(f"{gas_token}-{quote_1}", Decimal(str(gas_price)))
            rate_source.add_rate(f"{gas_token}-{quote_2}", Decimal(str(gas_price)))
            rate_source.add_rate(f"{quote_1}-{gas_token}", Decimal(str(1 / gas_price)))
            rate_source.add_rate(f"{quote_2}-{gas_token}", Decimal(str(1 / gas_price)))

    self.strategy = AmmArbStrategy()
    self.strategy.init_params(market_info_1=market_info_1,
                              market_info_2=market_info_2,
                              min_profitability=min_profitability,
                              order_amount=order_amount,
                              market_1_slippage_buffer=market_1_slippage_buffer,
                              market_2_slippage_buffer=market_2_slippage_buffer,
                              concurrent_orders_submission=concurrent_orders_submission,
                              rate_source=rate_source,
                              )
