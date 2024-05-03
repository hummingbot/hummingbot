import os
from decimal import Decimal
from typing import Dict, List, Set

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.core.data_type.common import PriceType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class V2XEMMConfig(StrategyV2ConfigBase):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    markets: Dict[str, Set[str]] = {}
    maker_connector: str = Field(
        default="kucoin",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the maker connector: ",
            prompt_on_new=True
        ))
    maker_trading_pair: str = Field(
        default="LBR-USDT",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the maker trading pair: ",
            prompt_on_new=True
        ))
    taker_connector: str = Field(
        default="okx",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the taker connector: ",
            prompt_on_new=True
        ))
    taker_trading_pair: str = Field(
        default="LBR-USDT",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the taker trading pair: ",
            prompt_on_new=True
        ))
    target_profitability: Decimal = Field(
        default=0.006,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the target profitability: ",
            prompt_on_new=True
        ))
    min_profitability: Decimal = Field(
        default=0.003,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the minimum profitability: ",
            prompt_on_new=True
        ))
    max_profitability: Decimal = Field(
        default=0.008,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the maximum profitability: ",
            prompt_on_new=True
        ))
    order_amount_quote: Decimal = Field(
        default=100,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the order amount in quote asset: ",
            prompt_on_new=True
        ))


class V2XEMM(StrategyV2Base):
    @classmethod
    def init_markets(cls, config: V2XEMMConfig):
        cls.markets = {config.maker_connector: {config.maker_trading_pair}, config.taker_connector: {config.taker_trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: V2XEMMConfig):
        super().__init__(connectors, config)
        self.config = config

    def determine_executor_actions(self) -> List[ExecutorAction]:
        executor_actions = []
        all_executors = self.get_all_executors()
        mid_price = self.market_data_provider.get_price_by_type(self.config.maker_connector, self.config.maker_trading_pair, PriceType.MidPrice)
        active_buy_executors = self.filter_executors(
            executors=all_executors,
            filter_func=lambda e: not e.is_done and e.config.maker_side == TradeType.BUY
        )
        active_sell_executors = self.filter_executors(
            executors=all_executors,
            filter_func=lambda e: not e.is_done and e.config.maker_side == TradeType.SELL
        )
        if len(active_buy_executors) == 0:
            config = XEMMExecutorConfig(
                timestamp=self.current_timestamp,
                buying_market=ConnectorPair(connector_name=self.config.maker_connector,
                                            trading_pair=self.config.maker_trading_pair),
                selling_market=ConnectorPair(connector_name=self.config.taker_connector,
                                             trading_pair=self.config.taker_trading_pair),
                maker_side=TradeType.BUY,
                order_amount=self.config.order_amount_quote / mid_price,
                min_profitability=self.config.min_profitability,
                target_profitability=self.config.target_profitability,
                max_profitability=self.config.max_profitability
            )
            executor_actions.append(CreateExecutorAction(executor_config=config))
        if len(active_sell_executors) == 0:
            config = XEMMExecutorConfig(
                timestamp=self.current_timestamp,
                buying_market=ConnectorPair(connector_name=self.config.taker_connector,
                                            trading_pair=self.config.taker_trading_pair),
                selling_market=ConnectorPair(connector_name=self.config.maker_connector,
                                             trading_pair=self.config.maker_trading_pair),
                maker_side=TradeType.SELL,
                order_amount=self.config.order_amount_quote / mid_price,
                min_profitability=self.config.min_profitability,
                target_profitability=self.config.target_profitability,
                max_profitability=self.config.max_profitability
            )
            executor_actions.append(CreateExecutorAction(executor_config=config))
        return executor_actions

    def format_status(self) -> str:
        original_status = super().format_status()
        xemm_data = []
        for ex in self.executor_orchestrator.executors["main"]:
            xemm_data.append(ex.to_format_status())
        return f"{original_status}\n\n" + '\n'.join(xemm_data)
