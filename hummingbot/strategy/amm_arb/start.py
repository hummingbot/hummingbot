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
    connector_1 = amm_arb_config_map.get("connector_1").value.lower()
    market_1 = amm_arb_config_map.get("market_1").value
    connector_2 = amm_arb_config_map.get("connector_2").value.lower()
    market_2 = amm_arb_config_map.get("market_2").value
    pool_id = "_" + amm_arb_config_map.get("pool_id").value
    order_amount = amm_arb_config_map.get("order_amount").value
    min_profitability = amm_arb_config_map.get("min_profitability").value / Decimal("100")
    market_1_slippage_buffer = amm_arb_config_map.get("market_1_slippage_buffer").value / Decimal("100")
    market_2_slippage_buffer = amm_arb_config_map.get("market_2_slippage_buffer").value / Decimal("100")
    concurrent_orders_submission = amm_arb_config_map.get("concurrent_orders_submission").value
    debug_price_shim = amm_arb_config_map.get("debug_price_shim").value
    gateway_transaction_cancel_interval = amm_arb_config_map.get("gateway_transaction_cancel_interval").value
    rate_oracle_enabled = amm_arb_config_map.get("rate_oracle_enabled").value
    quote_conversion_rate = amm_arb_config_map.get("quote_conversion_rate").value

    self._initialize_markets([(connector_1, [market_1]), (connector_2, [market_2])])
    base_1, quote_1 = market_1.split("-")
    base_2, quote_2 = market_2.split("-")

    is_connector_1_gateway = connector_1 in sorted(AllConnectorSettings.get_gateway_amm_connector_names())

    is_connector_2_gateway = connector_2 in sorted(AllConnectorSettings.get_gateway_amm_connector_names())

    market_info_1 = MarketTradingPairTuple(
        self.markets[connector_1], market_1 if not is_connector_1_gateway else market_1 + pool_id, base_1, quote_1
    )
    market_info_2 = MarketTradingPairTuple(
        self.markets[connector_2], market_2 if not is_connector_2_gateway else market_2 + pool_id, base_2, quote_2
    )
    self.market_trading_pair_tuples = [market_info_1, market_info_2]

    if debug_price_shim:
        amm_market_info: MarketTradingPairTuple = market_info_1
        other_market_info: MarketTradingPairTuple = market_info_2
        other_market_name: str = connector_2
        if AmmArbStrategy.is_gateway_market(other_market_info):
            amm_market_info = market_info_2
            other_market_info = market_info_1
            other_market_name = connector_1
        if Chain.ETHEREUM.chain == amm_market_info.market.chain:
            amm_connector: GatewayEVMAMM = cast(GatewayEVMAMM, amm_market_info.market)
        elif Chain.TEZOS.chain == amm_market_info.market.chain:
            amm_connector: GatewayTezosAMM = cast(GatewayTezosAMM, amm_market_info.market)
        elif Chain.TELOS.chain == amm_market_info.market.chain:
            amm_connector: GatewayTelosAMM = cast(GatewayTelosAMM, amm_market_info.market)
        else:
            raise ValueError(f"Unsupported chain: {amm_market_info.market.chain}")
        GatewayPriceShim.get_instance().patch_prices(
            other_market_name,
            other_market_info.trading_pair,
            amm_connector.connector_name,
            amm_connector.chain,
            amm_connector.network,
            amm_market_info.trading_pair
        )

    if rate_oracle_enabled:
        rate_source = RateOracle.get_instance()
    else:
        rate_source = FixedRateSource()
        rate_source.add_rate(f"{quote_2}-{quote_1}", Decimal(str(quote_conversion_rate)))   # reverse rate is already handled in FixedRateSource find_rate method.
        rate_source.add_rate(f"{quote_1}-{quote_2}", Decimal(str(1 / quote_conversion_rate)))   # reverse rate is already handled in FixedRateSource find_rate method.

    self.strategy = AmmArbStrategy()
    self.strategy.init_params(market_info_1=market_info_1,
                              market_info_2=market_info_2,
                              min_profitability=min_profitability,
                              order_amount=order_amount,
                              market_1_slippage_buffer=market_1_slippage_buffer,
                              market_2_slippage_buffer=market_2_slippage_buffer,
                              concurrent_orders_submission=concurrent_orders_submission,
                              gateway_transaction_cancel_interval=gateway_transaction_cancel_interval,
                              rate_source=rate_source,
                              )
