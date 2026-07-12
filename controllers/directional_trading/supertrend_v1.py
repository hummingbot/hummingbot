from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class SuperTrendConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "supertrend_v1"
    candles_connector: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "请输入 K 线数据连接器；留空则使用交易连接器：",
            "prompt_on_new": True})
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "请输入 K 线交易对；留空则使用当前交易对：",
            "prompt_on_new": True})
    interval: str = Field(
        default="3m",
        json_schema_extra={"prompt": "请输入 K 线周期（例如 1m、5m、1h、1d）：", "prompt_on_new": True})
    length: int = Field(
        default=20,
        json_schema_extra={"prompt": "请输入超级趋势计算长度：", "prompt_on_new": True})
    multiplier: float = Field(
        default=4.0,
        json_schema_extra={"prompt": "请输入超级趋势倍数：", "prompt_on_new": True})
    percentage_threshold: float = Field(
        default=0.01,
        json_schema_extra={"prompt": "请输入百分比阈值：", "prompt_on_new": True})

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


class SuperTrend(DirectionalTradingControllerBase):
    def __init__(self, config: SuperTrendConfig, *args, **kwargs):
        self.config = config
        self.max_records = config.length + 10
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        df = self.calculate_features(
            df,
            length=self.config.length,
            multiplier=self.config.multiplier,
            percentage_threshold=self.config.percentage_threshold,
        )

        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df

    @staticmethod
    def calculate_features(df, length: int, multiplier: float, percentage_threshold: float):
        """计算无空值的超级趋势特征，保证回测合并不会把所有 K 线删除。"""
        df = df.copy()
        df.ta.supertrend(length=length, multiplier=multiplier, append=True)
        indicator_columns = [column for column in df.columns if column.startswith("SUPERT")]
        df[indicator_columns] = df[indicator_columns].fillna(0)
        trend_column = f"SUPERT_{length}_{multiplier}"
        direction_column = f"SUPERTd_{length}_{multiplier}"
        df["percentage_distance"] = abs(df["close"] - df[trend_column]) / df["close"]

        long_condition = (df[direction_column] == 1) & (df["percentage_distance"] < percentage_threshold)
        short_condition = (df[direction_column] == -1) & (df["percentage_distance"] < percentage_threshold)

        df['signal'] = 0
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        return df

    def get_candles_config(self) -> List[CandlesConfig]:
        return [CandlesConfig(
            connector=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.max_records
        )]
