import os
from decimal import Decimal
from typing import Dict, List, Set

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class V2ArbitrageConfig(StrategyV2ConfigBase):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    markets: Dict[str, Set[str]] = {}
    cex_connector: str = Field(
        default="binance",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the CEX connector: ",
            prompt_on_new=True
        ))
    cex_pair: str = Field(
        default="MATIC-USDT",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the trading pair on the CEX connector: ",
            prompt_on_new=True
        ))
    amm_connector: str = Field(
        default="uniswap_polygon_mainnet",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the AMM connector: ",
            prompt_on_new=True
        ))
    amm_pair: str = Field(
        default="WMATIC-USDT",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the trading pair on the AMM connector: ",
            prompt_on_new=True
        ))
    min_profitability: Decimal = Field(
        default=0.003,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the minimum profitability: ",
            prompt_on_new=True
        ))
    order_amount_quote: Decimal = Field(
        default=100,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the order amount in quote asset: ",
            prompt_on_new=True
        ))
    cex_slippage_buffer: Decimal = Field(
        default=0.01,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the slippage buffer to apply on the CEX connector when executing trades: ",
            prompt_on_new=False
        ))
    amm_slippage_buffer: Decimal = Field(
        default=0.01,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the slippage buffer to apply on the AMM connector when executing trades: ",
            prompt_on_new=False
        ))


class V2Arbitrage(StrategyV2Base):
    @classmethod
    def init_markets(cls, config: V2ArbitrageConfig):
        cls.markets = {config.cex_connector: {config.cex_pair}, config.amm_connector: {config.amm_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: V2ArbitrageConfig):
        super().__init__(connectors, config)
        self.config = config

    def determine_executor_actions(self) -> List[ExecutorAction]:
        executor_actions = []
        all_executors = self.get_all_executors()

        cex_price = self.market_data_provider.get_price_by_type(self.config.cex_connector, self.config.cex_pair, PriceType.MidPrice)
        active_executors = self.filter_executors(
            executors=all_executors,
            # filter_func=lambda e: e.arbitrage_status in [ArbitrageExecutorStatus.NOT_STARTED, ArbitrageExecutorStatus.ACTIVE_ARBITRAGE]
            filter_func=lambda e: not e.is_done
        )

        cex_market = ConnectorPair(connector_name=self.config.cex_connector, trading_pair=self.config.cex_pair)
        amm_market = ConnectorPair(connector_name=self.config.amm_connector, trading_pair=self.config.amm_pair)

        if len(active_executors) == 0:
            config = ArbitrageExecutorConfig(
                timestamp=self.current_timestamp,
                buying_market=cex_market,
                selling_market=amm_market,
                order_amount=self.config.order_amount_quote / cex_price,
                min_profitability=self.config.min_profitability,
                buying_market_slippage_buffer=self.config.cex_slippage_buffer,
                selling_market_slippage_buffer=self.config.amm_slippage_buffer
            )
            executor_actions.append(CreateExecutorAction(executor_config=config))
            config = ArbitrageExecutorConfig(
                timestamp=self.current_timestamp,
                buying_market=amm_market,
                selling_market=cex_market,
                order_amount=self.config.order_amount_quote / cex_price,
                min_profitability=self.config.min_profitability,
                buying_market_slippage_buffer=self.config.amm_slippage_buffer,
                selling_market_slippage_buffer=self.config.cex_slippage_buffer
            )
            executor_actions.append(CreateExecutorAction(executor_config=config))

        return executor_actions

    def format_status(self) -> str:
        original_status = super().format_status()
        arbitrage_data = []
        for ex in self.executor_orchestrator.executors["main"]:
            arbitrage_data.append(ex.to_format_status())
        return f"{original_status}\n\n" + '\n'.join(arbitrage_data)
