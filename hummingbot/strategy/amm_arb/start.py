import asyncio
import time
from decimal import Decimal
from typing import cast

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.connector.gateway.amm.gateway_telos_amm import GatewayTelosAMM
from hummingbot.connector.gateway.amm.gateway_tezos_amm import GatewayTezosAMM
from hummingbot.connector.gateway.common_types import Chain
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.rate_conversion import RateConversionOracle


async def get_native_chain_token(market):
    await market.get_gas_estimate()
    gas_token_amount = market.network_transaction_fee
    gas_token, _ = gas_token_amount.token, gas_token_amount.amount
    return gas_token


async def await_trading_pairs_fetcher(self, exchange_list):
    """
    Wait for the TradingPairFetcher to fetch all trading pairs from the exchanges in exchange_list
    :param exchange_list: List of exchanges to fetch trading pairs from
    """
    from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
    trading_pair_fetcher = TradingPairFetcher.get_instance()

    # Fetch all trading pairs from the exchanges in exchange_list
    if not all(exchange in trading_pair_fetcher.trading_pairs.keys() for exchange in exchange_list):
        safe_ensure_future(trading_pair_fetcher.fetch_all_list(exchange_list))

    start_time = time.time()
    timeout = 120  # 2 minutes

    while not all(exchange in trading_pair_fetcher.trading_pairs.keys() for exchange in exchange_list):
        missing_exchanges = set(exchange_list) - set(trading_pair_fetcher.trading_pairs.keys())
        self.logger().info(f"Waiting for trading pairs to be fetched from {missing_exchanges}, don't start the bot yet...")

        # Check if the timeout has been reached
        if time.time() - start_time > timeout:
            self.logger().warning("Timeout of 2 minutes reached. Proceeding without all trading pairs.")
            break

        await asyncio.sleep(3)


async def async_start(self):
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
    fixed_conversion_rate_dict = dict(amm_arb_config_map.get("fixed_conversion_rate_dict").value)
    rate_conversion_exchanges = amm_arb_config_map.get("rate_conversion_exchanges").value

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
        # await the initialization of the markets in rate_conversion_exchanges on the TradingPairFetcher
        await await_trading_pairs_fetcher(self, rate_conversion_exchanges)

        base_1, quote_1 = market_1.split("-")
        base_2, quote_2 = market_2.split("-")

        market_info_1 = MarketTradingPairTuple(self.markets[connector_1], market_1, base_1, quote_1)
        market_info_2 = MarketTradingPairTuple(self.markets[connector_2], market_2, base_2, quote_2)
        self.market_trading_pair_tuples = [market_info_1, market_info_2]

        asset_set = set()
        asset_set.add(base_1)
        asset_set.add(base_2)
        asset_set.add(quote_1)
        asset_set.add(quote_2)

        # get native token of the chain and add it to asset_set, this is needed for the fee calculation
        for market_info in self.market_trading_pair_tuples:
            if isinstance(market_info.market, GatewayEVMAMM):
                native_token = await get_native_chain_token(market_info.market)
                asset_set.add(native_token)

        rate_source = RateConversionOracle(asset_set, self.client_config_map, rate_conversion_exchanges)

        for pair, rate in fixed_conversion_rate_dict.items():
            rate_source.add_fixed_asset_price_delegate(pair, Decimal(rate))

        # add to markets
        for conversion_pair, market in rate_source.markets.items():
            self.markets[conversion_pair] = market

    else:
        rate_source = FixedRateSource()
        rate_source.add_rate(f"{quote_2}-{quote_1}", Decimal(str(quote_conversion_rate)))  # reverse rate is already handled in FixedRateSource find_rate method.
        rate_source.add_rate(f"{quote_1}-{quote_2}", Decimal(str(1 / quote_conversion_rate)))  # reverse rate is already handled in FixedRateSource find_rate method.

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


def start(self):
    safe_ensure_future(async_start(self))
