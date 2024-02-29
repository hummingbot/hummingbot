import time
from decimal import Decimal
from typing import List

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig


class PMMSimpleConfig(MarketMakingControllerConfigBase):
    controller_name = "pmm_simple"
    # As this controller is a simple version of the PMM, we are not using the candles feed
    candles_config: List[CandlesConfig] = Field(default=[], client_data=ClientFieldData(prompt_on_new=False))


class PMMSimpleController(MarketMakingControllerBase):
    def __init__(self, config: PMMSimpleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=time.time(),
            level_id=level_id,
            exchange=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )
