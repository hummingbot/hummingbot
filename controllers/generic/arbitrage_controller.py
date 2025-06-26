from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import MarketDict
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class ArbitrageControllerConfig(ControllerConfigBase):
    controller_name: str = "arbitrage_controller"
    candles_config: List[CandlesConfig] = []
    exchange_pair_1: ConnectorPair = ConnectorPair(connector_name="binance", trading_pair="PENGU-USDT")
    exchange_pair_2: ConnectorPair = ConnectorPair(connector_name="solana_jupiter_mainnet-beta", trading_pair="PENGU-USDC")
    min_profitability: Decimal = Decimal("0.01")
    delay_between_executors: int = 10  # in seconds
    max_executors_imbalance: int = 1
    rate_connector: str = "binance"
    quote_conversion_asset: str = "USDT"
    interchange_tokens_for_price_fetch: Dict[str, str] = {}
    uniswap_slippage: Optional[Decimal] = None

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return [markets.add_or_update(cp.connector_name, cp.trading_pair) for cp in [self.exchange_pair_1, self.exchange_pair_2]][-1]


class ArbitrageController(ControllerBase):
    gas_token_by_network = {
        "ethereum": "BERA",
        "solana": "SOL",
        "binance-smart-chain": "BNB",
        "polygon": "POL",
        "avalanche": "AVAX",
        "dexalot": "AVAX"
    }

    def __init__(self, config: ArbitrageControllerConfig, *args, **kwargs):
        self.config = config
        super().__init__(config, *args, **kwargs)
        self._imbalance = 0
        self._last_buy_closed_timestamp = 0
        self._last_sell_closed_timestamp = 0
        self._len_active_buy_arbitrages = 0
        self._len_active_sell_arbitrages = 0
        self.base_asset = self.config.exchange_pair_1.trading_pair.split("-")[0]
        self.initialize_rate_sources()

    def _get_interchanged_trading_pair(self, trading_pair: str) -> str:
        base, quote = trading_pair.split("-")
        interchange_map = self.config.interchange_tokens_for_price_fetch
        if base in interchange_map:
            base = interchange_map[base]
        if quote in interchange_map:
            quote = interchange_map[quote]
        return f"{base}-{quote}"

    def initialize_rate_sources(self):
        rates_required = []
        for connector_pair in [self.config.exchange_pair_1, self.config.exchange_pair_2]:
            base, quote = connector_pair.trading_pair.split("-")
            # Add rate source for gas token
            if connector_pair.is_amm_connector():
                gas_token = self.get_gas_token(connector_pair.connector_name)
                if gas_token != quote:
                    trading_pair = f"{gas_token}-{quote}"
                    rates_required.append(ConnectorPair(connector_name=self.config.rate_connector,
                                                        trading_pair=self._get_interchanged_trading_pair(trading_pair)))

            # Add rate source for quote conversion asset
            if quote != self.config.quote_conversion_asset:
                trading_pair = f"{quote}-{self.config.quote_conversion_asset}"
                rates_required.append(ConnectorPair(connector_name=self.config.rate_connector,
                                                    trading_pair=self._get_interchanged_trading_pair(trading_pair)))

            # Add rate source for trading pairs
            rates_required.append(ConnectorPair(connector_name=connector_pair.connector_name,
                                                trading_pair=connector_pair.trading_pair))
        if len(rates_required) > 0:
            self.market_data_provider.initialize_rate_sources(rates_required)

    def get_gas_token(self, connector_name: str) -> str:
        _, chain, _ = connector_name.split("_")
        return self.gas_token_by_network[chain]

    async def update_processed_data(self):
        pass

    def determine_executor_actions(self) -> List[ExecutorAction]:
        self.update_arbitrage_stats()
        executor_actions = []
        current_time = self.market_data_provider.time()
        if (abs(self._imbalance) >= self.config.max_executors_imbalance or
                self._last_buy_closed_timestamp + self.config.delay_between_executors > current_time or
                self._last_sell_closed_timestamp + self.config.delay_between_executors > current_time):
            return executor_actions

        if self._len_active_buy_arbitrages == 0:
            buy_action = self.create_arbitrage_executor_action(self.config.exchange_pair_1, self.config.exchange_pair_2)
            if buy_action:
                self.logger().info(f"Creating buy arbitrage executor: {buy_action.executor_config.id}")
                executor_actions.append(buy_action)

        if self._len_active_sell_arbitrages == 0:
            sell_action = self.create_arbitrage_executor_action(self.config.exchange_pair_2, self.config.exchange_pair_1)
            if sell_action:
                self.logger().info(f"Creating sell arbitrage executor: {sell_action.executor_config.id}")
                executor_actions.append(sell_action)

        return executor_actions

    def create_arbitrage_executor_action(self, buying_exchange_pair: ConnectorPair,
                                         selling_exchange_pair: ConnectorPair):
        try:
            if buying_exchange_pair.is_amm_connector():
                gas_token = self.get_gas_token(buying_exchange_pair.connector_name)
                self.logger().info(f"Gas token: {gas_token}")
                pair = buying_exchange_pair.trading_pair.split("-")[0] + "-" + gas_token
                self.logger().info(f"DEBUG: Pair: {pair}")
                self.logger().info(f"Interchanged pair: {self._get_interchanged_trading_pair(pair)}")
                gas_conversion_price = self.market_data_provider.get_rate(self._get_interchanged_trading_pair(pair))
                self.logger().info(f"Gas conversion price: {pair} {gas_conversion_price}")
            elif selling_exchange_pair.is_amm_connector():
                gas_token = self.get_gas_token(selling_exchange_pair.connector_name)
                self.logger().info(f"Gas token: {gas_token}")
                pair = selling_exchange_pair.trading_pair.split("-")[0] + "-" + gas_token
                self.logger().info(f"DEBUG: Pair: {pair}")
                self.logger().info(f"Interchanged pair: {self._get_interchanged_trading_pair(pair)}")
                gas_conversion_price = self.market_data_provider.get_rate(self._get_interchanged_trading_pair(pair))
                self.logger().info(f"Gas conversion price: {pair} {gas_conversion_price}")
            else:
                gas_conversion_price = None
            rate_pair = self.base_asset + "-" + self.config.quote_conversion_asset
            rate = self.market_data_provider.get_rate(self._get_interchanged_trading_pair(rate_pair))
            amount_quantized = self.market_data_provider.quantize_order_amount(
                buying_exchange_pair.connector_name, buying_exchange_pair.trading_pair,
                self.config.total_amount_quote / rate)
            arbitrage_config = ArbitrageExecutorConfig(
                timestamp=self.market_data_provider.time(),
                buying_market=buying_exchange_pair,
                selling_market=selling_exchange_pair,
                order_amount=amount_quantized,
                min_profitability=self.config.min_profitability,
                slippage=self.config.uniswap_slippage,
                gas_conversion_price=gas_conversion_price,
                interchange_tokens_for_price_fetch=self.config.interchange_tokens_for_price_fetch,
            )
            return CreateExecutorAction(
                executor_config=arbitrage_config,
                controller_id=self.config.id)
        except Exception as e:
            self.logger().error(
                f"Error creating executor to buy on {buying_exchange_pair.connector_name} and sell on {selling_exchange_pair.connector_name}, {e}")

    def update_arbitrage_stats(self):
        closed_executors = [e for e in self.executors_info if e.status == RunnableStatus.TERMINATED]
        active_executors = [e for e in self.executors_info if e.status != RunnableStatus.TERMINATED]
        buy_arbitrages = [arbitrage for arbitrage in closed_executors if
                          arbitrage.config.buying_market == self.config.exchange_pair_1]
        sell_arbitrages = [arbitrage for arbitrage in closed_executors if
                           arbitrage.config.buying_market == self.config.exchange_pair_2]
        self._imbalance = len(buy_arbitrages) - len(sell_arbitrages)
        self._last_buy_closed_timestamp = max([arbitrage.close_timestamp for arbitrage in buy_arbitrages]) if len(
            buy_arbitrages) > 0 else 0
        self._last_sell_closed_timestamp = max([arbitrage.close_timestamp for arbitrage in sell_arbitrages]) if len(
            sell_arbitrages) > 0 else 0
        self._len_active_buy_arbitrages = len([arbitrage for arbitrage in active_executors if
                                               arbitrage.config.buying_market == self.config.exchange_pair_1])
        self._len_active_sell_arbitrages = len([arbitrage for arbitrage in active_executors if
                                                arbitrage.config.buying_market == self.config.exchange_pair_2])

    def to_format_status(self) -> List[str]:
        all_executors_custom_info = pd.DataFrame(e.custom_info for e in self.executors_info)
        return [format_df_for_printout(all_executors_custom_info, table_format="psql", )]
