from decimal import Decimal
from typing import List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction, StopExecutorAction


class DManMakerV2Config(MarketMakingControllerConfigBase):
    """
    Configuration required to run the D-Man Maker V2 strategy.
    """
    controller_name: str = "dman_maker_v2"

    # DCA configuration
    dca_spreads: List[Decimal] = Field(
        default="0.01,0.02,0.04,0.08",
        json_schema_extra={"prompt": "Enter a comma-separated list of spreads for each DCA level: ", "prompt_on_new": True})
    dca_amounts: List[Decimal] = Field(
        default="0.1,0.2,0.4,0.8",
        json_schema_extra={"prompt": "Enter a comma-separated list of amounts for each DCA level: ", "prompt_on_new": True})
    top_executor_refresh_time: Optional[float] = Field(default=None, json_schema_extra={"is_updatable": True})
    executor_activation_bounds: Optional[List[Decimal]] = Field(default=None, json_schema_extra={"is_updatable": True})

    @field_validator("executor_activation_bounds", mode="before")
    @classmethod
    def parse_activation_bounds(cls, v):
        if isinstance(v, list):
            return [Decimal(val) for val in v]
        elif isinstance(v, str):
            if v == "":
                return None
            return [Decimal(val) for val in v.split(",")]
        return v

    @field_validator('dca_spreads', mode="before")
    @classmethod
    def parse_dca_spreads(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            spreads = [Decimal(x.strip()) for x in v.split(',')]
        elif isinstance(v, list):
            spreads = [Decimal(str(x)) for x in v]
        else:
            spreads = [Decimal(str(v))]
        if any(x <= 0 for x in spreads):
            raise ValueError("dca_spreads must contain positive numbers.")
        return spreads

    @field_validator('dca_amounts', mode="before")
    @classmethod
    def parse_and_validate_dca_amounts(cls, v, validation_info):
        spreads = validation_info.data.get('dca_spreads', [])
        if v is None or v == "":
            amounts = [Decimal("1") for _ in spreads]
        elif isinstance(v, str):
            amounts = [Decimal(x.strip()) for x in v.split(',')]
        elif isinstance(v, list):
            amounts = [Decimal(str(x)) for x in v]
        else:
            amounts = [Decimal(str(v))]

        if len(amounts) != len(spreads):
            raise ValueError(
                f"The number of dca amounts ({len(amounts)}) must match the number of dca spreads ({len(spreads)}).")
        if any(x <= 0 for x in amounts):
            raise ValueError("dca_amounts must contain positive numbers.")
        if sum(amounts) <= 0:
            raise ValueError("The sum of dca_amounts must be greater than zero.")
        return amounts


class DManMakerV2(MarketMakingControllerBase):
    def __init__(self, config: DManMakerV2Config, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        total_dca_amount = sum(self.config.dca_amounts) if self.config.dca_amounts else Decimal("0")
        if total_dca_amount > Decimal("0"):
            self.dca_amounts_pct = [Decimal(str(amount)) / total_dca_amount for amount in self.config.dca_amounts]
        elif len(self.config.dca_amounts) > 0:
            self.dca_amounts_pct = [Decimal("1") / Decimal(len(self.config.dca_amounts)) for _ in self.config.dca_amounts]
        else:
            self.dca_amounts_pct = []
        self.spreads = self.config.dca_spreads

    def first_level_refresh_condition(self, executor):
        if self.config.top_executor_refresh_time is not None:
            if self.get_level_from_level_id(executor.custom_info["level_id"]) == 0:
                return self.market_data_provider.time() - executor.timestamp > self.config.top_executor_refresh_time
        return False

    def order_level_refresh_condition(self, executor):
        return self.market_data_provider.time() - executor.timestamp > self.config.executor_refresh_time

    def executors_to_refresh(self) -> List[ExecutorAction]:
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: not x.is_trading and x.is_active and (self.order_level_refresh_condition(x) or self.first_level_refresh_condition(x)))
        return [StopExecutorAction(
            controller_id=self.config.id,
            executor_id=executor.id) for executor in executors_to_refresh]

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        if trade_type == TradeType.BUY:
            prices = [price * (1 - spread) for spread in self.spreads]
        else:
            prices = [price * (1 + spread) for spread in self.spreads]
        amounts = [amount * pct for pct in self.dca_amounts_pct]
        amounts_quote = [amount * price for amount, price in zip(amounts, prices)]
        return DCAExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            mode=DCAMode.MAKER,
            side=trade_type,
            prices=prices,
            amounts_quote=amounts_quote,
            level_id=level_id,
            time_limit=self.config.time_limit,
            stop_loss=self.config.stop_loss,
            take_profit=self.config.take_profit,
            trailing_stop=self.config.trailing_stop,
            activation_bounds=self.config.executor_activation_bounds,
            leverage=self.config.leverage,
        )
