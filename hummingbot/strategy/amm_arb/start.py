from decimal import Decimal
from typing import cast

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.connector.gateway.amm.gateway_telos_amm import GatewayTelosAMM
from hummingbot.connector.gateway.amm.gateway_tezos_amm import GatewayTezosAMM
from hummingbot.connector.gateway.common_types import Chain
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    num_exchanges = amm_arb_config_map.get("number_of_exchanges").value
    market_pair = amm_arb_config_map.get("market_pair").value
    connectors = []
    slippage_buffers = {}
    for i in range(num_exchanges):
        connector = amm_arb_config_map.get(f"connector_{i+1}").value.lower()
        connectors.append(connector)
    pool_id = "_" + amm_arb_config_map.get("pool_id").value
    order_amount = amm_arb_config_map.get("order_amount").value
    min_profitability = amm_arb_config_map.get("min_profitability").value / Decimal("100")
    concurrent_orders_submission = amm_arb_config_map.get("concurrent_orders_submission").value
    debug_price_shim = amm_arb_config_map.get("debug_price_shim").value
    gateway_transaction_cancel_interval = amm_arb_config_map.get("gateway_transaction_cancel_interval").value
    rate_oracle_enabled = amm_arb_config_map.get("rate_oracle_enabled").value
    quote_conversion_rate = amm_arb_config_map.get("quote_conversion_rate").value

    market_configs = [(connector, [market_pair]) for connector in connectors]
    self._initialize_markets(market_configs)

    base, quote = market_pair.split("-")
    market_tuples = []
    for i, connector in enumerate(connectors):
        is_gateway = connector in sorted(AllConnectorSettings.get_gateway_amm_connector_names())
        trading_pair = market_pair + pool_id if is_gateway else market_pair
        market_tuple = MarketTradingPairTuple(self.markets[connector], trading_pair, base, quote)
        market_tuples.append(market_tuple)

    for i in range(num_exchanges):
        slippage = amm_arb_config_map.get(f"connector_{i+1}_slippage_buffer").value / Decimal("100")
        slippage_buffers[market_tuples[i]] = slippage
    self.market_trading_pair_tuples = market_tuples
    if debug_price_shim:
        for market_info in market_tuples:
            if AmmArbStrategy.is_gateway_market(market_info):
                if Chain.ETHEREUM.chain == market_info.market.chain:
                    amm_connector = cast(GatewayEVMAMM, market_info.market)
                elif Chain.TEZOS.chain == market_info.market.chain:
                    amm_connector = cast(GatewayTezosAMM, market_info.market)
                elif Chain.TELOS.chain == market_info.market.chain:
                    amm_connector = cast(GatewayTelosAMM, market_info.market)
                else:
                    raise ValueError(f"Unsupported chain: {market_info.market.chain}")
                for other_market_info in market_tuples:
                    if not AmmArbStrategy.is_gateway_market(other_market_info):
                        GatewayPriceShim.get_instance().patch_prices(
                            other_market_info.market.name,
                            other_market_info.trading_pair,
                            amm_connector.connector_name,
                            amm_connector.chain,
                            amm_connector.network,
                            market_info.trading_pair,
                        )

    if rate_oracle_enabled:
        rate_source = RateOracle.get_instance()
    else:
        rate_source = FixedRateSource()
        rate_source.add_rate(
            f"{quote}-{quote}", Decimal(str(quote_conversion_rate))
        )  # reverse rate is already handled in FixedRateSource find_rate method.
    self.strategy = AmmArbStrategy()
    self.strategy.init_params(
        market_infos=self.market_trading_pair_tuples,
        min_profitability=min_profitability,
        order_amount=order_amount,
        slippage_buffers=slippage_buffers,
        concurrent_orders_submission=concurrent_orders_submission,
        gateway_transaction_cancel_interval=gateway_transaction_cancel_interval,
        rate_source=rate_source,
    )
