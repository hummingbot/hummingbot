from decimal import Decimal
from typing import List

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
        },
    )
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",
            "prompt_on_new": True,
        },
    )
    interval: str = Field(
        default="30m",
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True,
        },
    )
    bb_length: int = Field(
        default=100,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands length: ",
            "prompt_on_new": True,
        },
    )
    bb_std: float = Field(
        default=2.0,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands standard deviation: ",
        },
    )
    bb_long_threshold: float = Field(
        default=0.0,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands long threshold: ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )
    bb_short_threshold: float = Field(
        default=1.0,
        json_schema_extra={
            "prompt": "Enter the Bollinger Bands short threshold: ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )
    macd_fast: int = Field(
        default=21,
        json_schema_extra={
            "prompt": "Enter the MACD fast period: ",
            "prompt_on_new": True,
        },
    )
    macd_slow: int = Field(
        default=42,
        json_schema_extra={
            "prompt": "Enter the MACD slow period: ",
            "prompt_on_new": True,
        },
    )
    macd_signal: int = Field(
        default=9,
        json_schema_extra={
            "prompt": "Enter the MACD signal period: ",
            "prompt_on_new": True,
        },
    )
    dynamic_order_spread: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Enable dynamic order spread: ",
            "prompt_on_new": True,
        },
    )
    dynamic_target: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Enable dynamic target: ",
            "prompt_on_new": True,
        },
    )

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
            self.config.candles_config = [
                CandlesConfig(
                    connector=config.candles_connector,
                    trading_pair=config.candles_trading_pair,
                    interval=config.interval,
                    max_records=self.max_records,
                )
            ]
        super().__init__(config, *args, **kwargs)

        self._volatility: float = 0.0
        # pandas_ta bbands(std=X) produces columns like BBB_{length}_{std}_{std}
        self._bb_suffix = f"{self.config.bb_length}_{self.config.bb_std}_{self.config.bb_std}"

    def get_candles_config(self):
        return self.config.candles_config

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(
            connector_name=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.max_records,
        )
        # Add indicators
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)
        df.ta.natr(length=self.config.bb_length)
        df.ta.macd(fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal, append=True)
        df.ta.adx(length=self.config.bb_length, append=True)
        df.ta.aroon(length=self.config.macd_fast // 2, append=True)
        df.ta.aroon(length=self.config.macd_fast, append=True)
        df.ta.aroon(length=self.config.macd_fast * 2, append=True)
        df.ta.aroon(length=self.config.macd_fast * 4, append=True)

        macd_col = f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"
        macds_col = f"MACDs_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"
        aroon_0 = df[f"AROONOSC_{self.config.macd_fast // 2}"]
        aroon_1 = df[f"AROONOSC_{self.config.macd_fast}"]
        aroon_2 = df[f"AROONOSC_{self.config.macd_fast * 2}"]

        df["MACD>S"] = 0
        df.loc[df[macd_col] > df[macds_col], "MACD>S"] = 1
        df["MACD_cross"] = df["MACD>S"].diff()

        long_condition = (df["MACD>S"] == 1) & (aroon_0 > 0) & (aroon_1 > 0) & (aroon_2 > 0)
        short_condition = (df["MACD>S"] == 0) & (aroon_0 < 0) & (aroon_1 < 0) & (aroon_2 < 0)

        df["signal"] = 0
        df.loc[long_condition, "signal"] = -1
        df.loc[short_condition, "signal"] = 1

        df["volatility"] = df[f"BBB_{self._bb_suffix}"] / self.config.bb_std / 100
        if df["volatility"].iloc[-1] != 0:
            volatility_update = abs((df["volatility"].iloc[-1] - self._volatility) / df["volatility"].iloc[-1]) > 0.01
            self._volatility = df["volatility"].iloc[-1]
        else:
            volatility_update = False

        new_signal = df["signal"].iloc[-1]
        prev_signal = self.processed_data.get("signal", 0)
        self.processed_data["signal"] = new_signal
        self.processed_data["volatility_update"] = volatility_update
        self.processed_data["volatility"] = df["volatility"].iloc[-1]

        if new_signal != prev_signal:
            self.logger().info(
                f"Signal changed: {prev_signal} -> {new_signal} "
                f"({'LONG' if new_signal == -1 else 'SHORT' if new_signal == 1 else 'NEUTRAL'})"
            )
        if self.processed_data["volatility_update"]:
            self.logger().info(f"Volatility: {self.processed_data['volatility']:.4g}")

        self.processed_data["features"] = df[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                f"BBP_{self._bb_suffix}",
                f"BBB_{self._bb_suffix}",
                "MACD>S",
                f"AROONOSC_{self.config.macd_fast // 2}",
                f"AROONOSC_{self.config.macd_fast}",
                f"AROONOSC_{self.config.macd_fast * 2}",
                "signal",
            ]
        ]

    def get_spread_multiplier(self) -> Decimal:
        if self.config.dynamic_order_spread:
            df = self.processed_data["features"]
            bb_width = df[f"BBB_{self._bb_suffix}"].iloc[-1]
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
                take_profit_table=self.config.trailing_stop.take_profit_table,
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
