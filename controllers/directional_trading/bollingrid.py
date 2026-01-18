from decimal import Decimal
from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig


class BollinGridControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "bollingrid"
    candles_config: List[CandlesConfig] = []
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
        default="3m",
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True})
    bb_length: int = Field(
        default=100,
        json_schema_extra={"prompt": "Enter the Bollinger Bands length: ", "prompt_on_new": True})
    bb_std: float = Field(default=2.0)
    bb_long_threshold: float = Field(default=0.0)
    bb_short_threshold: float = Field(default=1.0)

    # Grid-specific parameters
    grid_start_price_coefficient: float = Field(
        default=0.25,
        json_schema_extra={"prompt": "Grid start price coefficient (multiplier of BB width): ", "prompt_on_new": True})
    grid_end_price_coefficient: float = Field(
        default=0.75,
        json_schema_extra={"prompt": "Grid end price coefficient (multiplier of BB width): ", "prompt_on_new": True})
    grid_limit_price_coefficient: float = Field(
        default=0.35,
        json_schema_extra={"prompt": "Grid limit price coefficient (multiplier of BB width): ", "prompt_on_new": True})
    min_spread_between_orders: Decimal = Field(
        default=Decimal("0.005"),
        json_schema_extra={"prompt": "Minimum spread between grid orders (e.g., 0.005 for 0.5%): ", "prompt_on_new": True})
    order_frequency: int = Field(
        default=2,
        json_schema_extra={"prompt": "Order frequency (seconds between grid orders): ", "prompt_on_new": True})
    max_orders_per_batch: int = Field(
        default=1,
        json_schema_extra={"prompt": "Maximum orders per batch: ", "prompt_on_new": True})
    min_order_amount_quote: Decimal = Field(
        default=Decimal("6"),
        json_schema_extra={"prompt": "Minimum order amount in quote currency: ", "prompt_on_new": True})
    max_open_orders: int = Field(
        default=5,
        json_schema_extra={"prompt": "Maximum number of open orders: ", "prompt_on_new": True})

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


class BollinGridController(DirectionalTradingControllerBase):
    def __init__(self, config: BollinGridControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = self.config.bb_length
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        # Add indicators
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)
        bbp = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"]
        bb_width = df[f"BBB_{self.config.bb_length}_{self.config.bb_std}"]

        # Generate signal
        long_condition = bbp < self.config.bb_long_threshold
        short_condition = bbp > self.config.bb_short_threshold

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1
        signal = df["signal"].iloc[-1]
        close = df["close"].iloc[-1]
        current_bb_width = bb_width.iloc[-1] / 100
        if signal == -1:
            end_price = close * (1 + current_bb_width * self.config.grid_start_price_coefficient)
            start_price = close * (1 - current_bb_width * self.config.grid_end_price_coefficient)
            limit_price = close * (1 + current_bb_width * self.config.grid_limit_price_coefficient)
        elif signal == 1:
            start_price = close * (1 - current_bb_width * self.config.grid_start_price_coefficient)
            end_price = close * (1 + current_bb_width * self.config.grid_end_price_coefficient)
            limit_price = close * (1 - current_bb_width * self.config.grid_limit_price_coefficient)
        else:
            start_price = None
            end_price = None
            limit_price = None

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
        self.processed_data["grid_params"] = {
            "start_price": start_price,
            "end_price": end_price,
            "limit_price": limit_price
        }

    def get_executor_config(self, trade_type: TradeType, price: Decimal, amount: Decimal):
        """
        Get the grid executor config based on the trade_type, price and amount.
        Uses configurable grid parameters from the controller config.
        """
        return GridExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            start_price=self.processed_data["grid_params"]["start_price"],
            end_price=self.processed_data["grid_params"]["end_price"],
            limit_price=self.processed_data["grid_params"]["limit_price"],
            side=trade_type,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            min_spread_between_orders=self.config.min_spread_between_orders,
            total_amount_quote=amount * price,
            order_frequency=self.config.order_frequency,
            max_orders_per_batch=self.config.max_orders_per_batch,
            min_order_amount_quote=self.config.min_order_amount_quote,
            max_open_orders=self.config.max_open_orders,
        )
