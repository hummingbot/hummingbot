from decimal import Decimal
from typing import List

import pandas as pd
from pydantic import Field, field_validator

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.controllers import DirectionalTradingControllerBase, DirectionalTradingControllerConfigBase
from hummingbot.strategy_v2.executors.progressive_executor.data_types import (
    LadderedTrailingStop,
    ProgressiveExecutorConfig,
    YieldTripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class ProgressiveTradingControllerConfig(DirectionalTradingControllerConfigBase):
    controller_type: str = "progressive_trading"

    @field_validator("manual_kill_switch", mode="before")
    @classmethod
    def coerce_manual_kill_switch(cls, v):
        if v is None:
            return False
        return v

    apr_yield: Decimal | None = Field(
        default=Decimal("0.5"), gt=0,
        json_schema_extra={
            "prompt": "Enter the APR yield (as a decimal, e.g., 0.5 for 50%): ",
            "prompt_on_new": True,
            "is_updatable": True,
        })
    trailing_stop: LadderedTrailingStop | None = Field(
        default="0.015,0.005,0.05:1|0.1:0.91|0.25:0.8|0.5:0.5",
        json_schema_extra={
            "prompt": "Enter the trailing stop as activation_pnl_pct,trailing_pct,profit_table (e.g., 0.015,0.003,0.05:1|0.1:0.91): ",
            "prompt_on_new": True,
        })

    @field_validator("trailing_stop", mode="before")
    @classmethod
    def parse_trailing_stop(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
            activation_pnl_pct, trailing_pct, *take_profit_table = v.split(",")
            take_profit_table = tuple(map(lambda x: tuple(map(Decimal, x.split(":"))), take_profit_table[0].split("|")))
            return LadderedTrailingStop(
                activation_pnl_pct=Decimal(activation_pnl_pct),
                trailing_pct=Decimal(trailing_pct),
                take_profit_table=take_profit_table
            )
        return v

    @field_validator("apr_yield", mode="before")
    @classmethod
    def validate_apr_yield(cls, v):
        if isinstance(v, str):
            return None if v == "" else Decimal(v)
        return v

    @property
    def triple_barrier_config(self) -> YieldTripleBarrierConfig:
        return YieldTripleBarrierConfig(
            apr_yield=self.apr_yield,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            trailing_stop=self.trailing_stop,
            open_order_type=OrderType.MARKET,
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,
            time_limit_order_type=OrderType.MARKET
        )


class ProgressiveTradingController(DirectionalTradingControllerBase):
    def __init__(self, config: ProgressiveTradingControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)

    def determine_executor_actions(self) -> List[ExecutorAction]:
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    def get_executor_config(self, trade_type: TradeType, price: Decimal, amount: Decimal) -> ProgressiveExecutorConfig:
        return ProgressiveExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            side=trade_type,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
        )

    def to_format_status(self) -> List[str]:
        df = self.processed_data.get("features", pd.DataFrame())
        if df.empty:
            return []
        return [format_df_for_printout(df.tail(1), table_format="psql",)]
