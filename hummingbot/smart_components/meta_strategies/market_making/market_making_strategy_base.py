from typing import List

from pydantic import BaseModel

from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.meta_strategies.data_types import OrderLevel
from hummingbot.smart_components.meta_strategies.market_making.market_maker_executor import MetaStrategyMode
from hummingbot.smart_components.meta_strategies.meta_strategy_base import MetaStrategyBase


class MarketMakingStrategyConfigBase(BaseModel):
    strategy_name: str
    exchange: str
    trading_pair: str
    order_refresh_time: int = 60
    cooldown_time: int = 0
    order_levels: List[OrderLevel]


class MarketMakingStrategyBase(MetaStrategyBase[MarketMakingStrategyConfigBase]):
    def __init__(self, config: MarketMakingStrategyConfigBase, candles_config: List[CandlesConfig],
                 mode: MetaStrategyMode = MetaStrategyMode.LIVE):
        super().__init__(config, mode)
        self.candles = self.initialize_candles(candles_config)

    def initialize_candles(self, candles_config: List[CandlesConfig]):
        if self.mode == MetaStrategyMode.LIVE:
            return [CandlesFactory.get_candle(candles_config) for candles_config in candles_config]
        else:
            raise NotImplementedError

    def start(self):
        for candle in self.candles:
            candle.start()

    def stop(self):
        for candle in self.candles:
            candle.stop()

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.config.exchange

    @property
    def all_candles_ready(self):
        """
        Checks if the candlesticks are full.
        """
        return all([candle.is_ready for candle in self.candles])

    def get_order_levels(self) -> List[OrderLevel]:
        raise NotImplementedError

    def refresh_order_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def early_stop_condition(self, executor: PositionExecutor) -> bool:
        raise NotImplementedError

    def cooldown_condition(self, executor: PositionExecutor) -> bool:
        raise NotImplementedError

    def get_position_config(self, order_level: OrderLevel) -> PositionConfig:
        raise NotImplementedError
