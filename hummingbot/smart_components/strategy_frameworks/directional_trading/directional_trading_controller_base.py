import time
from decimal import Decimal
from typing import List, Optional, Set

import pandas as pd
from pydantic import Field

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase, ControllerConfigBase


class DirectionalTradingControllerConfigBase(ControllerConfigBase):
    exchange: str = Field(default="binance_perpetual")
    trading_pair: str = Field(default="BTC-USDT")
    order_levels: List[OrderLevel]
    leverage: int = Field(10, ge=1)
    position_mode: PositionMode = Field(PositionMode.HEDGE)


class DirectionalTradingControllerBase(ControllerBase):

    def __init__(self,
                 config: DirectionalTradingControllerConfigBase,
                 excluded_parameters: Optional[List[str]] = None):
        super().__init__(config, excluded_parameters)
        self.config = config  # this is only for type hints

    def filter_executors_df(self, df):
        return df[df["trading_pair"] == self.config.trading_pair]

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self.config.exchange not in markets_dict:
            markets_dict[self.config.exchange] = {self.config.trading_pair}
        else:
            markets_dict[self.config.exchange].add(self.config.trading_pair)
        return markets_dict

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        # TODO: Refactor this as a method of the base class that receives the exchange name as a parameter
        return "perpetual" in self.config.exchange

    def get_signal(self):
        df = self.get_processed_data()
        return df["signal"].iloc[-1]

    def get_spread_multiplier(self):
        df = self.get_processed_data()
        if "target" in df.columns:
            return Decimal(df["target"].iloc[-1])
        else:
            return Decimal("1.0")

    def early_stop_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def cooldown_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def get_position_config(self, order_level: OrderLevel, signal: int) -> PositionExecutorConfig:
        """
        Creates a PositionConfig object from an OrderLevel object.
        Here you can use technical indicators to determine the parameters of the position config.
        """
        if (signal == 1 and order_level.side == TradeType.BUY) or (signal == -1 and order_level.side == TradeType.SELL):
            # Here you can use the weight of the signal to tweak for example the order amount
            close_price = self.get_close_price(self.close_price_trading_pair)
            amount = order_level.order_amount_usd / close_price
            spread_multiplier = self.get_spread_multiplier()
            order_price = close_price * (1 + order_level.spread_factor * spread_multiplier * signal)
            if order_level.triple_barrier_conf.trailing_stop_trailing_delta and order_level.triple_barrier_conf.trailing_stop_trailing_delta:
                trailing_stop = TrailingStop(
                    activation_price=order_level.triple_barrier_conf.trailing_stop_activation_price,
                    trailing_delta=order_level.triple_barrier_conf.trailing_stop_trailing_delta,
                )
            else:
                trailing_stop = None
            position_config = PositionExecutorConfig(
                timestamp=time.time(),
                trading_pair=self.config.trading_pair,
                exchange=self.config.exchange,
                side=order_level.side,
                amount=amount,
                take_profit=order_level.triple_barrier_conf.take_profit,
                stop_loss=order_level.triple_barrier_conf.stop_loss,
                time_limit=order_level.triple_barrier_conf.time_limit,
                entry_price=Decimal(order_price),
                open_order_type=order_level.triple_barrier_conf.open_order_type,
                take_profit_order_type=order_level.triple_barrier_conf.take_profit_order_type,
                trailing_stop=trailing_stop,
                leverage=self.config.leverage
            )
            return position_config

    def get_processed_data(self) -> pd.DataFrame:
        """
        Retrieves the processed dataframe with indicators, signal, weight and spreads multipliers.
        Returns:
            pd.DataFrame: The processed dataframe with indicators, signal, weight and spreads multipliers.
        """
        raise NotImplementedError

    def to_format_status(self) -> list:
        lines = super().to_format_status()
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "signal"] + self.extra_columns_to_show()
        df = self.get_processed_data()
        prices_str = format_df_for_printout(df[columns_to_show].tail(4), table_format="psql")
        lines.extend([f"{prices_str}"])
        return lines

    def extra_columns_to_show(self):
        return []
