import time
from decimal import Decimal
from typing import Dict, List, Optional, Set

import pandas as pd
from pydantic import Field, field_validator

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class XEMMMultipleLevelsConfig(ControllerConfigBase):
    controller_name: str = "xemm_multiple_levels"
    candles_config: List[CandlesConfig] = []
    maker_connector: str = Field(
        default="mexc",
        json_schema_extra={"prompt": "Enter the maker connector: ", "prompt_on_new": True})
    maker_trading_pair: str = Field(
        default="PEPE-USDT",
        json_schema_extra={"prompt": "Enter the maker trading pair: ", "prompt_on_new": True})
    taker_connector: str = Field(
        default="binance",
        json_schema_extra={"prompt": "Enter the taker connector: ", "prompt_on_new": True})
    taker_trading_pair: str = Field(
        default="PEPE-USDT",
        json_schema_extra={"prompt": "Enter the taker trading pair: ", "prompt_on_new": True})
    buy_levels_targets_amount: List[List[Decimal]] = Field(
        default="0.003,10-0.006,20-0.009,30",
        json_schema_extra={
            "prompt": "Enter the buy levels targets with the following structure: (target_profitability1,amount1-target_profitability2,amount2): ",
            "prompt_on_new": True})
    sell_levels_targets_amount: List[List[Decimal]] = Field(
        default="0.003,10-0.006,20-0.009,30",
        json_schema_extra={
            "prompt": "Enter the sell levels targets with the following structure: (target_profitability1,amount1-target_profitability2,amount2): ",
            "prompt_on_new": True})
    min_profitability: Decimal = Field(
        default=0.003,
        json_schema_extra={"prompt": "Enter the minimum profitability: ", "prompt_on_new": True})
    max_profitability: Decimal = Field(
        default=0.01,
        json_schema_extra={"prompt": "Enter the maximum profitability: ", "prompt_on_new": True})
    max_executors_imbalance: int = Field(
        default=1,
        json_schema_extra={"prompt": "Enter the maximum executors imbalance: ", "prompt_on_new": True})

    @field_validator("buy_levels_targets_amount", "sell_levels_targets_amount", mode="before")
    @classmethod
    def validate_levels_targets_amount(cls, v):
        if isinstance(v, str):
            v = [list(map(Decimal, x.split(","))) for x in v.split("-")]
        return v

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.maker_connector not in markets:
            markets[self.maker_connector] = set()
        markets[self.maker_connector].add(self.maker_trading_pair)
        if self.taker_connector not in markets:
            markets[self.taker_connector] = set()
        markets[self.taker_connector].add(self.taker_trading_pair)
        return markets


class XEMMMultipleLevels(ControllerBase):

    def __init__(self, config: XEMMMultipleLevelsConfig, *args, **kwargs):
        self.config = config
        self.buy_levels_targets_amount = config.buy_levels_targets_amount
        self.sell_levels_targets_amount = config.sell_levels_targets_amount
        super().__init__(config, *args, **kwargs)
        self._gas_token_cache = {}
        self._initialize_gas_tokens()
        self.initialize_rate_sources()

    def initialize_rate_sources(self):
        rates_required = []
        for connector_pair in [
            ConnectorPair(connector_name=self.config.maker_connector, trading_pair=self.config.maker_trading_pair),
            ConnectorPair(connector_name=self.config.taker_connector, trading_pair=self.config.taker_trading_pair)
        ]:
            base, quote = connector_pair.trading_pair.split("-")

            # Add rate source for gas token if it's an AMM connector
            if connector_pair.is_amm_connector():
                gas_token = self.get_gas_token(connector_pair.connector_name)
                if gas_token and gas_token != base and gas_token != quote:
                    rates_required.append(ConnectorPair(connector_name=self.config.maker_connector,
                                                        trading_pair=f"{base}-{gas_token}"))

            # Add rate source for trading pairs
            rates_required.append(connector_pair)

        if len(rates_required) > 0:
            self.market_data_provider.initialize_rate_sources(rates_required)

    def _initialize_gas_tokens(self):
        """Initialize gas tokens for AMM connectors during controller initialization."""
        import asyncio

        async def fetch_gas_tokens():
            for connector_name in [self.config.maker_connector, self.config.taker_connector]:
                connector_pair = ConnectorPair(connector_name=connector_name, trading_pair="")
                if connector_pair.is_amm_connector():
                    if connector_name not in self._gas_token_cache:
                        try:
                            gateway_client = GatewayHttpClient.get_instance()

                            # Get chain and network for the connector
                            chain, network, error = await gateway_client.get_connector_chain_network(
                                connector_name
                            )

                            if error:
                                self.logger().warning(f"Failed to get chain info for {connector_name}: {error}")
                                continue

                            # Get native currency symbol
                            native_currency = await gateway_client.get_native_currency_symbol(chain, network)

                            if native_currency:
                                self._gas_token_cache[connector_name] = native_currency
                                self.logger().info(f"Gas token for {connector_name}: {native_currency}")
                            else:
                                self.logger().warning(f"Failed to get native currency for {connector_name}")
                        except Exception as e:
                            self.logger().error(f"Error getting gas token for {connector_name}: {e}")

        # Run the async function to fetch gas tokens
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(fetch_gas_tokens())
        else:
            loop.run_until_complete(fetch_gas_tokens())

    def get_gas_token(self, connector_name: str) -> Optional[str]:
        """Get the cached gas token for a connector."""
        return self._gas_token_cache.get(connector_name)

    async def update_processed_data(self):
        pass

    def determine_executor_actions(self) -> List[ExecutorAction]:
        executor_actions = []
        mid_price = self.market_data_provider.get_price_by_type(self.config.maker_connector, self.config.maker_trading_pair, PriceType.MidPrice)
        active_buy_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: not e.is_done and e.config.maker_side == TradeType.BUY
        )
        active_sell_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: not e.is_done and e.config.maker_side == TradeType.SELL
        )
        stopped_buy_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: e.is_done and e.config.maker_side == TradeType.BUY and e.filled_amount_quote != 0
        )
        stopped_sell_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: e.is_done and e.config.maker_side == TradeType.SELL and e.filled_amount_quote != 0
        )
        imbalance = len(stopped_buy_executors) - len(stopped_sell_executors)

        # Calculate total amounts for proportional allocation
        total_buy_amount = sum(amount for _, amount in self.buy_levels_targets_amount)
        total_sell_amount = sum(amount for _, amount in self.sell_levels_targets_amount)

        # Allocate 50% of total_amount_quote to each side
        buy_side_quote = self.config.total_amount_quote * Decimal("0.5")
        sell_side_quote = self.config.total_amount_quote * Decimal("0.5")

        for target_profitability, amount in self.buy_levels_targets_amount:
            active_buy_executors_target = [e.config.target_profitability == target_profitability for e in active_buy_executors]

            if len(active_buy_executors_target) == 0 and imbalance < self.config.max_executors_imbalance:
                # Calculate proportional amount: (level_amount / total_side_amount) * (total_quote * 0.5)
                proportional_amount_quote = (amount / total_buy_amount) * buy_side_quote
                min_profitability = target_profitability - self.config.min_profitability
                max_profitability = target_profitability + self.config.max_profitability
                config = XEMMExecutorConfig(
                    controller_id=self.config.id,
                    timestamp=self.market_data_provider.time(),
                    buying_market=ConnectorPair(connector_name=self.config.maker_connector,
                                                trading_pair=self.config.maker_trading_pair),
                    selling_market=ConnectorPair(connector_name=self.config.taker_connector,
                                                 trading_pair=self.config.taker_trading_pair),
                    maker_side=TradeType.BUY,
                    order_amount=proportional_amount_quote / mid_price,
                    min_profitability=min_profitability,
                    target_profitability=target_profitability,
                    max_profitability=max_profitability
                )
                executor_actions.append(CreateExecutorAction(executor_config=config, controller_id=self.config.id))
        for target_profitability, amount in self.sell_levels_targets_amount:
            active_sell_executors_target = [e.config.target_profitability == target_profitability for e in active_sell_executors]
            if len(active_sell_executors_target) == 0 and imbalance > -self.config.max_executors_imbalance:
                # Calculate proportional amount: (level_amount / total_side_amount) * (total_quote * 0.5)
                proportional_amount_quote = (amount / total_sell_amount) * sell_side_quote
                min_profitability = target_profitability - self.config.min_profitability
                max_profitability = target_profitability + self.config.max_profitability
                config = XEMMExecutorConfig(
                    controller_id=self.config.id,
                    timestamp=time.time(),
                    buying_market=ConnectorPair(connector_name=self.config.taker_connector,
                                                trading_pair=self.config.taker_trading_pair),
                    selling_market=ConnectorPair(connector_name=self.config.maker_connector,
                                                 trading_pair=self.config.maker_trading_pair),
                    maker_side=TradeType.SELL,
                    order_amount=proportional_amount_quote / mid_price,
                    min_profitability=min_profitability,
                    target_profitability=target_profitability,
                    max_profitability=max_profitability
                )
                executor_actions.append(CreateExecutorAction(executor_config=config, controller_id=self.config.id))
        return executor_actions

    def to_format_status(self) -> List[str]:
        all_executors_custom_info = pd.DataFrame(e.custom_info for e in self.executors_info)
        return [format_df_for_printout(all_executors_custom_info, table_format="psql", )]
