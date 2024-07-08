import time
from decimal import Decimal
from typing import Dict, List, Set

import pandas as pd
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class XEMMMultipleLevelsConfig(ControllerConfigBase):
    controller_name: str = "xemm_multiple_levels"
    candles_config: List[CandlesConfig] = []
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
    buy_levels_targets_amount: List[List[Decimal]] = Field(
        default="0.003,10-0.006,20-0.009,30",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the buy levels targets with the following structure: (target_profitability1,amount1-target_profitability2,amount2): ",
            prompt_on_new=True
        ))
    sell_levels_targets_amount: List[List[Decimal]] = Field(
        default="0.003,10-0.006,20-0.009,30",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the sell levels targets with the following structure: (target_profitability1,amount1-target_profitability2,amount2): ",
            prompt_on_new=True
        ))
    min_profitability: Decimal = Field(
        default=0.002,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the minimum profitability: ",
            prompt_on_new=True
        ))
    max_profitability: Decimal = Field(
        default=0.01,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the maximum profitability: ",
            prompt_on_new=True
        ))
    max_executors_imbalance: int = Field(
        default=1,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the maximum executors imbalance: ",
            prompt_on_new=True
        ))

    @validator("buy_levels_targets_amount", "sell_levels_targets_amount", pre=True, always=True)
    def validate_levels_targets_amount(cls, v, values):
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
        for target_profitability, amount in self.buy_levels_targets_amount:
            active_buy_executors_target = [e.config.target_profitability == target_profitability for e in active_buy_executors]

            if len(active_buy_executors_target) == 0 and imbalance < self.config.max_executors_imbalance:
                config = XEMMExecutorConfig(
                    controller_id=self.config.id,
                    timestamp=self.market_data_provider.time(),
                    buying_market=ConnectorPair(connector_name=self.config.maker_connector,
                                                trading_pair=self.config.maker_trading_pair),
                    selling_market=ConnectorPair(connector_name=self.config.taker_connector,
                                                 trading_pair=self.config.taker_trading_pair),
                    maker_side=TradeType.BUY,
                    order_amount=amount / mid_price,
                    min_profitability=self.config.min_profitability,
                    target_profitability=target_profitability,
                    max_profitability=self.config.max_profitability
                )
                executor_actions.append(CreateExecutorAction(executor_config=config, controller_id=self.config.id))
        for target_profitability, amount in self.sell_levels_targets_amount:
            active_sell_executors_target = [e.config.target_profitability == target_profitability for e in active_sell_executors]
            if len(active_sell_executors_target) == 0 and imbalance > -self.config.max_executors_imbalance:
                config = XEMMExecutorConfig(
                    controller_id=self.config.id,
                    timestamp=time.time(),
                    buying_market=ConnectorPair(connector_name=self.config.taker_connector,
                                                trading_pair=self.config.taker_trading_pair),
                    selling_market=ConnectorPair(connector_name=self.config.maker_connector,
                                                 trading_pair=self.config.maker_trading_pair),
                    maker_side=TradeType.SELL,
                    order_amount=amount / mid_price,
                    min_profitability=self.config.min_profitability,
                    target_profitability=target_profitability,
                    max_profitability=self.config.max_profitability
                )
                executor_actions.append(CreateExecutorAction(executor_config=config, controller_id=self.config.id))
        return executor_actions

    def to_format_status(self) -> List[str]:
        all_executors_custom_info = pd.DataFrame(e.custom_info for e in self.executors_info)
        return [format_df_for_printout(all_executors_custom_info, table_format="psql", )]
