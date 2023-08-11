from decimal import Decimal
from typing import List, Set

from pydantic import BaseModel

from hummingbot.core.data_type.common import PositionMode
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.meta_strategies.data_types import MetaStrategyMode, OrderLevel
from hummingbot.smart_components.meta_strategies.meta_strategy_base import MetaStrategyBase


class MarketMakingStrategyConfigBase(BaseModel):
    strategy_name: str
    exchange: str
    trading_pair: str
    order_levels: List[OrderLevel]
    candles_config: List[CandlesConfig]
    leverage: int = 10
    position_mode: PositionMode = PositionMode.HEDGE


class MarketMakingStrategyBase(MetaStrategyBase[MarketMakingStrategyConfigBase]):
    def __init__(self, config: MarketMakingStrategyConfigBase, mode: MetaStrategyMode = MetaStrategyMode.LIVE):
        super().__init__(config, mode)
        self.candles = self.initialize_candles(config.candles_config)

    def initialize_candles(self, candles_config: List[CandlesConfig]):
        if self.mode == MetaStrategyMode.LIVE:
            return [CandlesFactory.get_candle(candles_config) for candles_config in candles_config]
        else:
            raise NotImplementedError

    def get_close_price(self, connector: str, trading_pair: str):
        """
        Gets the close price of the last candlestick.
        """
        candles = self.get_candles_by_connector_trading_pair(connector, trading_pair)
        first_candle = list(candles.values())[0]
        return Decimal(first_candle.candles_df["close"].iloc[-1])

    def get_price_and_spread_multiplier(self):
        """
        Gets the price and spread multiplier from the last candlestick.
        """
        candles_df = self.get_candles_with_price_and_spread_multipiers()
        return Decimal(candles_df["price_multiplier"].iloc[-1]), Decimal(candles_df["spread_multiplier"].iloc[-1])

    def get_candles_dict(self) -> dict:
        candles = {candle.name: {} for candle in self.candles}
        for candle in self.candles:
            candles[candle.name][candle.interval] = candle
        return candles

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self.config.exchange not in markets_dict:
            markets_dict[self.config.exchange] = {self.config.trading_pair}
        else:
            markets_dict[self.config.exchange].add(self.config.trading_pair)
        return markets_dict

    def get_candle(self, connector: str, trading_pair: str, interval: str):
        """
        Gets the candlestick with the given connector, trading pair and interval.
        """
        return self.get_candles_by_connector_trading_pair(connector, trading_pair)[interval]

    def get_candles_by_connector_trading_pair(self, connector: str, trading_pair: str):
        """
        Gets all the candlesticks with the given connector and trading pair.
        """
        candle_name = f"{connector}_{trading_pair}"
        return self.get_candles_dict()[candle_name]

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

    def refresh_order_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def early_stop_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def cooldown_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def get_position_config(self, order_level: OrderLevel) -> PositionConfig:
        """
        Creates a PositionConfig object from an OrderLevel object.
        Here you can use technical indicators to determine the parameters of the position config.
        """
        raise NotImplementedError

    def get_candles_with_price_and_spread_multipiers(self):
        raise NotImplementedError
