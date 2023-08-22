from decimal import Decimal
from typing import List, Optional, Set

from hummingbot.core.data_type.common import PositionMode
from hummingbot.smart_components.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.data_types import ControllerMode, OrderLevel
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor


class MarketMakingControllerConfigBase(ControllerConfigBase):
    exchange: str
    trading_pair: str
    leverage: int = 10
    position_mode: PositionMode = PositionMode.HEDGE


class MarketMakingControllerBase(ControllerBase):

    def __init__(self,
                 config: MarketMakingControllerConfigBase,
                 mode: ControllerMode = ControllerMode.LIVE,
                 excluded_parameters: Optional[List[str]] = None):
        super().__init__(config, mode, excluded_parameters)
        self._config = config  # this is only for type hints

    def get_price_and_spread_multiplier(self):
        """
        Gets the price and spread multiplier from the last candlestick.
        """
        candles_df = self.get_candles_with_price_and_spread_multipliers()
        return Decimal(candles_df["price_multiplier"].iloc[-1]), Decimal(candles_df["spread_multiplier"].iloc[-1])

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self._config.exchange not in markets_dict:
            markets_dict[self._config.exchange] = {self._config.trading_pair}
        else:
            markets_dict[self._config.exchange].add(self._config.trading_pair)
        return markets_dict

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self._config.exchange

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

    def get_candles_with_price_and_spread_multipliers(self):
        raise NotImplementedError
