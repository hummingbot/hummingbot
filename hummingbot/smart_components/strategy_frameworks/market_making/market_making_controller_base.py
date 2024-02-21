from decimal import Decimal
from typing import Dict, List, Optional, Set

from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase, ControllerConfigBase


class MarketMakingControllerConfigBase(ControllerConfigBase):
    exchange: str
    trading_pair: str
    leverage: int = 10
    order_levels: List[OrderLevel]
    position_mode: PositionMode = PositionMode.HEDGE
    global_trailing_stop_config: Optional[Dict[TradeType, TrailingStop]] = None


class MarketMakingControllerBase(ControllerBase):

    def __init__(self,
                 config: MarketMakingControllerConfigBase,
                 excluded_parameters: Optional[List[str]] = None):
        super().__init__(config, excluded_parameters)
        self.config = config  # this is only for type hints

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.config.exchange

    def get_balance_required_by_order_levels(self):
        """
        Get the balance required by the order levels.
        """
        sell_amount = sum([order_level.order_amount_usd for order_level in self.config.order_levels if order_level.side == TradeType.SELL])
        buy_amount = sum([order_level.order_amount_usd for order_level in self.config.order_levels if order_level.side == TradeType.BUY])
        return {TradeType.SELL: sell_amount, TradeType.BUY: buy_amount}

    def filter_executors_df(self, df):
        return df[df["trading_pair"] == self.config.trading_pair]

    def get_price_and_spread_multiplier(self):
        """
        Gets the price and spread multiplier from the last candlestick.
        """
        candles_df = self.get_processed_data()
        return Decimal(candles_df["price_multiplier"].iloc[-1]), Decimal(candles_df["spread_multiplier"].iloc[-1])

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self.config.exchange not in markets_dict:
            markets_dict[self.config.exchange] = {self.config.trading_pair}
        else:
            markets_dict[self.config.exchange].add(self.config.trading_pair)
        return markets_dict

    def refresh_order_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def early_stop_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def cooldown_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def get_position_config(self, order_level: OrderLevel) -> PositionExecutorConfig:
        """
        Creates a PositionConfig object from an OrderLevel object.
        Here you can use technical indicators to determine the parameters of the position config.
        """
        raise NotImplementedError

    def get_processed_data(self):
        raise NotImplementedError
