from decimal import Decimal
from typing import List

import pandas as pd
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.models.executor_actions import StopExecutorAction


class MeanReversionV1ControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "mean_reversion_v1"
    candles_connector: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",
            "prompt_on_new": True})
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",
            "prompt_on_new": True})
    interval: str = Field(
        default="5m",
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True})
    lookback_period: int = Field(
        default=120,
        gt=10,
        json_schema_extra={
            "prompt": "Enter the fair value lookback period: ",
            "prompt_on_new": True,
            "is_updatable": True})
    entry_z_score: Decimal = Field(
        default=Decimal("2.0"),
        gt=0,
        json_schema_extra={
            "prompt": "Enter the z-score required to enter a position: ",
            "prompt_on_new": True,
            "is_updatable": True})
    exit_z_score: Decimal = Field(
        default=Decimal("0.25"),
        ge=0,
        json_schema_extra={
            "prompt": "Enter the z-score inside which active positions should be closed: ",
            "prompt_on_new": True,
            "is_updatable": True})
    use_ema: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Use EMA instead of SMA for fair value? ",
            "prompt_on_new": True,
            "is_updatable": True})
    rsi_length: int = Field(
        default=14,
        gt=1,
        json_schema_extra={
            "prompt": "Enter the RSI length: ",
            "prompt_on_new": True,
            "is_updatable": True})
    rsi_long_threshold: Decimal = Field(
        default=Decimal("35"),
        ge=0,
        le=100,
        json_schema_extra={
            "prompt": "Enter the maximum RSI allowed for long entries: ",
            "prompt_on_new": True,
            "is_updatable": True})
    rsi_short_threshold: Decimal = Field(
        default=Decimal("65"),
        ge=0,
        le=100,
        json_schema_extra={
            "prompt": "Enter the minimum RSI required for short entries: ",
            "prompt_on_new": True,
            "is_updatable": True})
    trend_filter_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Enable the trend regime filter? ",
            "prompt_on_new": True,
            "is_updatable": True})
    trend_ema_period: int = Field(
        default=200,
        gt=1,
        json_schema_extra={
            "prompt": "Enter the trend EMA period: ",
            "prompt_on_new": True,
            "is_updatable": True})
    max_trend_deviation: Decimal = Field(
        default=Decimal("0.015"),
        ge=0,
        json_schema_extra={
            "prompt": "Enter the maximum allowed distance from trend EMA, as a decimal: ",
            "prompt_on_new": True,
            "is_updatable": True})
    volume_lookback: int = Field(
        default=60,
        gt=1,
        json_schema_extra={
            "prompt": "Enter the volume lookback period: ",
            "prompt_on_new": True,
            "is_updatable": True})
    min_volume_ratio: Decimal = Field(
        default=Decimal("0.25"),
        ge=0,
        json_schema_extra={
            "prompt": "Enter the minimum volume ratio versus rolling average: ",
            "prompt_on_new": True,
            "is_updatable": True})
    min_std_pct: Decimal = Field(
        default=Decimal("0.001"),
        ge=0,
        json_schema_extra={
            "prompt": "Enter the minimum rolling standard deviation percentage: ",
            "prompt_on_new": True,
            "is_updatable": True})
    max_std_pct: Decimal = Field(
        default=Decimal("0.05"),
        gt=0,
        json_schema_extra={
            "prompt": "Enter the maximum rolling standard deviation percentage: ",
            "prompt_on_new": True,
            "is_updatable": True})
    close_on_mean_reversion: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Close active executors when price reverts to the exit z-score band? ",
            "prompt_on_new": True,
            "is_updatable": True})
    signal_on_closed_candle: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": "Generate signals from the last closed candle? ",
            "prompt_on_new": True,
            "is_updatable": True})

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

    @field_validator(
        "entry_z_score",
        "exit_z_score",
        "rsi_long_threshold",
        "rsi_short_threshold",
        "max_trend_deviation",
        "min_volume_ratio",
        "min_std_pct",
        "max_std_pct",
        mode="before")
    @classmethod
    def parse_decimal(cls, v):
        return Decimal(str(v)) if isinstance(v, (float, int, str)) else v


class MeanReversionV1Controller(DirectionalTradingControllerBase):
    def __init__(self, config: MeanReversionV1ControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = max(
            self.config.lookback_period,
            self.config.trend_ema_period,
            self.config.volume_lookback,
            self.config.rsi_length,
        ) + 25
        super().__init__(config, *args, **kwargs)

    def get_candles_config(self) -> List[CandlesConfig]:
        return [CandlesConfig(
            connector=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.max_records
        )]

    @staticmethod
    def _rsi(close: pd.Series, length: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        rs = gain / loss.where(loss != 0)
        return 100 - (100 / (1 + rs))

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(
            connector_name=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.max_records,
        ).copy()
        if self.config.signal_on_closed_candle and len(df) > 1:
            df = df.iloc[:-1].copy()

        close = df["close"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)
        lookback = self.config.lookback_period

        if self.config.use_ema:
            df["fair_value"] = close.ewm(span=lookback, adjust=False, min_periods=lookback).mean()
        else:
            df["fair_value"] = close.rolling(lookback, min_periods=lookback).mean()

        df["std"] = close.rolling(lookback, min_periods=lookback).std(ddof=0)
        df["z_score"] = (close - df["fair_value"]) / df["std"]
        df["std_pct"] = df["std"] / df["fair_value"]
        df["trend_ema"] = close.ewm(span=self.config.trend_ema_period, adjust=False, min_periods=self.config.trend_ema_period).mean()
        df["trend_deviation"] = (close - df["trend_ema"]).abs() / df["trend_ema"]
        df["volume_avg"] = volume.rolling(self.config.volume_lookback, min_periods=self.config.volume_lookback).mean()
        df["volume_ratio"] = volume / df["volume_avg"]
        df["rsi"] = self._rsi(close, self.config.rsi_length)

        long_condition = (
            (df["z_score"] <= -float(self.config.entry_z_score))
            & (df["rsi"] <= float(self.config.rsi_long_threshold))
        )
        short_condition = (
            (df["z_score"] >= float(self.config.entry_z_score))
            & (df["rsi"] >= float(self.config.rsi_short_threshold))
        )
        volatility_condition = (
            (df["std_pct"] >= float(self.config.min_std_pct))
            & (df["std_pct"] <= float(self.config.max_std_pct))
        )
        volume_condition = df["volume_ratio"] >= float(self.config.min_volume_ratio)

        if self.config.trend_filter_enabled:
            trend_condition = df["trend_deviation"] <= float(self.config.max_trend_deviation)
        else:
            trend_condition = pd.Series(True, index=df.index)

        df["signal"] = 0
        df.loc[long_condition & volatility_condition & volume_condition & trend_condition, "signal"] = 1
        df.loc[short_condition & volatility_condition & volume_condition & trend_condition, "signal"] = -1

        latest = df.iloc[-1]
        self.processed_data = {
            "signal": int(latest["signal"]) if pd.notna(latest["signal"]) else 0,
            "close_to_mean": bool(abs(float(latest["z_score"])) <= float(self.config.exit_z_score)) if pd.notna(latest["z_score"]) else False,
            "features": df,
        }

    def stop_actions_proposal(self):
        if not self.config.close_on_mean_reversion or not self.processed_data.get("close_to_mean", False):
            return []

        active_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda executor: executor.is_active,
        )
        return [
            StopExecutorAction(controller_id=self.config.id, executor_id=executor.id)
            for executor in active_executors
        ]

    def get_custom_info(self) -> dict:
        df = self.processed_data.get("features", pd.DataFrame())
        if df.empty:
            return {}
        latest = df.iloc[-1]
        return {
            "signal": self.processed_data.get("signal", 0),
            "z_score": float(latest["z_score"]) if pd.notna(latest["z_score"]) else None,
            "fair_value": float(latest["fair_value"]) if pd.notna(latest["fair_value"]) else None,
            "rsi": float(latest["rsi"]) if pd.notna(latest["rsi"]) else None,
            "volume_ratio": float(latest["volume_ratio"]) if pd.notna(latest["volume_ratio"]) else None,
            "std_pct": float(latest["std_pct"]) if pd.notna(latest["std_pct"]) else None,
        }
