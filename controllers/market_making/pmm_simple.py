import time
from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.executor_actions import ExecutorAction, StopExecutorAction


class PMMSimpleConfig(MarketMakingControllerConfigBase):
    controller_name = "pmm_simple"
    # As this controller is a simple version of the PMM, we are not using the candles feed
    candles_config: List[CandlesConfig] = Field(default=[], client_data=ClientFieldData(prompt_on_new=False))
    top_order_refresh_time: Optional[float] = Field(
        default=None,
        client_data=ClientFieldData(
            is_updatable=True,
            prompt_on_new=False))


class PMMSimpleController(MarketMakingControllerBase):
    def __init__(self, config: PMMSimpleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    def first_level_refresh_condition(self, executor):
        if self.config.top_order_refresh_time is not None:
            if self.get_level_from_level_id(executor.custom_info["level_id"]) == 1:
                return time.time() - executor.timestamp > self.config.top_order_refresh_time
        return False

    def order_level_refresh_condition(self, executor):
        return time.time() - executor.timestamp > self.config.executor_refresh_time

    def executors_to_refresh(self) -> List[ExecutorAction]:
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: not x.is_trading and x.is_active and (self.order_level_refresh_condition(x) or self.first_level_refresh_condition(x)))
        return [StopExecutorAction(
            controller_id=self.config.id,
            executor_id=executor.id) for executor in executors_to_refresh]

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=time.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )
