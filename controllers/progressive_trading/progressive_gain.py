from decimal import Decimal
from typing import List

import pandas as pd
import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.progressive_trading_controller import (
    ProgressiveTradingController,
    ProgressiveTradingControllerConfig,
)
from hummingbot.strategy_v2.executors.progressive_executor.data_types import (
    LadderedTrailingStop,
    ProgressiveExecutorConfig,
)


class ProgressiveGainControllerConfig(ProgressiveTradingControllerConfig):
    controller_name: str = "progressive_gain"
    candles_config: List[CandlesConfig] = []
    candles_connector: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",
            "prompt_on_new": True,
        })
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",
            "prompt_on_new": True,
        })
    interval: str = Field(
        default="30m",
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True,
        })
    bb_length: int = Field(
        default=100,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands length: ",
            "prompt_on_new": True,
        })
    bb_std: float = Field(
        default=2.0,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands standard deviation: ",
        })
    bb_long_threshold: float = Field(
        default=0.0,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands long threshold: ",
            "prompt_on_new": True,
            "is_updatable": True,
        })
    bb_short_threshold: float = Field(
        default=1.0,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands short threshold: ",
            "prompt_on_new": True,
            "is_updatable": True,
        })
    macd_fast: int = Field(
        default=21,
        json_schema_extra={
            "prompt": "Enter the MACD fast period: ",
            "prompt_on_new": True,
        })
    macd_slow: int = Field(
        default=42,
        json_schema_extra={
            "prompt": "Enter the MACD slow period: ",
            "prompt_on_new": True,
        })
    macd_signal: int = Field(
        default=9,
        json_schema_extra={
            "prompt": "Enter the MACD signal period: ",
            "prompt_on_new": True,
        })
    dynamic_order_spread: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Enable dynamic order spread: ",
            "prompt_on_new": True,
        })
    dynamic_target: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Enable dynamic target: ",
            "prompt_on_new": True,
        })

    @field_validator("candles_connector", mode="before")
    @classmethod
    def set_candles_connector(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("connector_name")
        return v

    @field_validator("candles_trading_pair", mode="before")
    @classmethod
    def set_candles_trading_pair(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("trading_pair")
        return v


class ProgressiveGainController(ProgressiveTradingController):
    """
    Mean reversion strategy with Grid execution making use of Bollinger Bands indicator to make spreads dynamic
    and shift the mid-price.
    """

    def __init__(self, config: ProgressiveGainControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = config.bb_length
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

        self._volatility: float = 0.0

    def get_candles_config(self):
        return self.config.candles_config

    async def update_processed_data(self):
        # no-op: signal=0, no TA processing (profiling moved to standalone background task)
        self.processed_data["signal"] = 0
        self.processed_data["features"] = pd.DataFrame()

    def get_spread_multiplier(self) -> Decimal:
        if self.config.dynamic_order_spread:
            df = self.processed_data["features"]
            bb_width = df[f"BBB_{self.config.bb_length}_{self.config.bb_std}"].iloc[-1]
            return Decimal(bb_width / 200)
        else:
            return Decimal("1.0")

    def get_executor_config(self, trade_type: TradeType, price: Decimal, amount: Decimal) -> ProgressiveExecutorConfig:
        spread_multiplier = self.get_spread_multiplier()
        if self.config.dynamic_target:
            stop_loss = self.config.stop_loss * spread_multiplier
            trailing_stop = LadderedTrailingStop(
                activation_pnl_pct=self.config.trailing_stop.activation_pnl_pct * spread_multiplier,
                trailing_pct=self.config.trailing_stop.trailing_pct * spread_multiplier,
                take_profit_table=self.config.trailing_stop.take_profit_table
            )
        else:
            stop_loss = self.config.stop_loss
            trailing_stop = self.config.trailing_stop

        triple_barrier = self.config.triple_barrier_config
        triple_barrier.stop_loss = stop_loss
        triple_barrier.trailing_stop = trailing_stop
        return ProgressiveExecutorConfig(
            timestamp=self.market_data_provider.time(),
            trading_pair=self.config.trading_pair,
            connector_name=self.config.connector_name,
            side=trade_type,
            entry_price=price,
            amount=amount,
            triple_barrier_config=triple_barrier,
            leverage=self.config.leverage,
        )
