from decimal import Decimal

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    market_pair = amm_arb_config_map.get("market_pair").value
    connectors = ["binance_paper_trade", "kucoin_paper_trade", "kraken_paper_trade"]
    slippage_buffer = Decimal("0.01")
    rebal_slippage_buffer = amm_arb_config_map.get("rebal_slippage_buffer").value / Decimal("100")
    pool_id = "_" + amm_arb_config_map.get("pool_id").value
    max_order_amount = amm_arb_config_map.get("max_order_amount").value
    min_profitability = amm_arb_config_map.get("min_profitability").value
    concurrent_orders_submission = amm_arb_config_map.get("concurrent_orders_submission").value
    gateway_transaction_cancel_interval = amm_arb_config_map.get("gateway_transaction_cancel_interval").value
    rate_oracle_enabled = amm_arb_config_map.get("rate_oracle_enabled").value
    quote_conversion_rate = amm_arb_config_map.get("quote_conversion_rate").value
    inventory_threshhold = amm_arb_config_map.get("inventory_threshhold").value

    market_configs = [(connector, [market_pair]) for connector in connectors]
    self._initialize_markets(market_configs)

    base, quote = market_pair.split("-")
    market_tuples = []
    for i, connector in enumerate(connectors):
        is_gateway = connector in sorted(AllConnectorSettings.get_gateway_amm_connector_names())
        trading_pair = market_pair + pool_id if is_gateway else market_pair
        market_tuple = MarketTradingPairTuple(self.markets[connector], trading_pair, base, quote)
        market_tuples.append(market_tuple)

    self.market_trading_pair_tuples = market_tuples
    if rate_oracle_enabled:
        rate_source = RateOracle.get_instance()
    else:
        rate_source = FixedRateSource()
        rate_source.add_rate(
            f"{quote}-{quote}", Decimal(str(quote_conversion_rate)))

    self.strategy = AmmArbStrategy()
    self.strategy.init_params(market_adapters=self.market_trading_pair_tuples,
                              min_profitability=min_profitability,
                              max_order_amount=max_order_amount,
                              rebal_slippage_buffer = rebal_slippage_buffer,
                              slippage_buffer=slippage_buffer,
                              concurrent_orders_submission=concurrent_orders_submission,
                              gateway_transaction_cancel_interval=gateway_transaction_cancel_interval,
                              rate_source=rate_source,
                              inventory_threshhold=inventory_threshhold)
