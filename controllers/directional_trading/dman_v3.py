import time
from decimal import Decimal
from typing import List, Optional, Tuple

import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop


class DManV3ControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "dman_v3"
    candles_config: List[CandlesConfig] = []
    candles_connector: str = Field(
        default=None,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",)
    )
    candles_trading_pair: str = Field(
        default=None,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",)
    )
    interval: str = Field(
        default="30m",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            prompt_on_new=True))
    bb_length: int = Field(
        default=100,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands length: ",
            prompt_on_new=True))
    bb_std: float = Field(
        default=2.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands standard deviation: ",
            prompt_on_new=False))
    bb_long_threshold: float = Field(
        default=0.0,
        client_data=ClientFieldData(
            is_updatable=True,
            prompt=lambda mi: "Enter the Bollinger Bands long threshold: ",
            prompt_on_new=True))
    bb_short_threshold: float = Field(
        default=1.0,
        client_data=ClientFieldData(
            is_updatable=True,
            prompt=lambda mi: "Enter the Bollinger Bands short threshold: ",
            prompt_on_new=True))
    dca_spreads: List[Decimal] = Field(
        default="0.001,0.018,0.15,0.25",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the spreads for each DCA level (comma-separated) if dynamic_spread=True this value "
                              "will multiply the Bollinger Bands width, e.g. if the Bollinger Bands width is 0.1 (10%)"
                              "and the spread is 0.2, the distance of the order to the current price will be 0.02 (2%) ",
            prompt_on_new=True))
    dca_amounts_pct: List[Decimal] = Field(
        default=None,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the amounts for each DCA level (as a percentage of the total balance, "
                              "comma-separated). Don't worry about the final sum, it will be normalized. ",
            prompt_on_new=True))
    dynamic_order_spread: bool = Field(
        default=None,
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to make the spread dynamic? (Yes/No) ",
            prompt_on_new=True))
    dynamic_target: bool = Field(
        default=None,
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to make the target dynamic? (Yes/No) ",
            prompt_on_new=True))

    activation_bounds: Optional[List[Decimal]] = Field(
        default=None,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the activation bounds for the orders "
                              "(e.g., 0.01 activates the next order when the price is closer than 1%): ",
            prompt_on_new=True))

    @validator("activation_bounds", pre=True, always=True)
    def parse_activation_bounds(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
            return [Decimal(val) for val in v.split(",")]
        if isinstance(v, list):
            return [Decimal(val) for val in v]
        return v

    @validator('dca_spreads', pre=True, always=True)
    def validate_spreads(cls, v):
        if isinstance(v, str):
            return [Decimal(val) for val in v.split(",")]
        return v

    @validator('dca_amounts_pct', pre=True, always=True)
    def validate_amounts(cls, v, values):
        spreads = values.get("dca_spreads")
        if isinstance(v, str):
            if v == "":
                return [Decimal('1.0') / len(spreads) for _ in spreads]
            amounts = [Decimal(val) for val in v.split(",")]
            if len(amounts) != len(spreads):
                raise ValueError("Amounts and spreads must have the same length")
            return amounts
        if v is None:
            return [Decimal('1.0') / len(spreads) for _ in spreads]
        return v

    def get_spreads_and_amounts_in_quote(self, trade_type: TradeType, total_amount_quote: Decimal) -> Tuple[List[Decimal], List[Decimal]]:
        amounts_pct = self.dca_amounts_pct
        if amounts_pct is None:
            # Equally distribute if amounts_pct is not set
            spreads = self.dca_spreads
            normalized_amounts_pct = [Decimal('1.0') / len(spreads) for _ in spreads]
        else:
            if trade_type == TradeType.BUY:
                normalized_amounts_pct = [amt_pct / sum(amounts_pct) for amt_pct in amounts_pct]
            else:  # TradeType.SELL
                normalized_amounts_pct = [amt_pct / sum(amounts_pct) for amt_pct in amounts_pct]

        return self.dca_spreads, [amt_pct * total_amount_quote for amt_pct in normalized_amounts_pct]

    @validator("candles_connector", pre=True, always=True)
    def set_candles_connector(cls, v, values):
        if v is None or v == "":
            return values.get("connector_name")
        return v

    @validator("candles_trading_pair", pre=True, always=True)
    def set_candles_trading_pair(cls, v, values):
        if v is None or v == "":
            return values.get("trading_pair")
        return v


class DManV3Controller(DirectionalTradingControllerBase):
    """
    Mean reversion strategy with Grid execution making use of Bollinger Bands indicator to make spreads dynamic
    and shift the mid-price.
    """
    def __init__(self, config: DManV3ControllerConfig, *args, **kwargs):
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

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        # Add indicators
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)

        # Generate signal
        long_condition = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"] < self.config.bb_long_threshold
        short_condition = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"] > self.config.bb_short_threshold

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df

    def get_spread_multiplier(self) -> Decimal:
        if self.config.dynamic_order_spread:
            df = self.processed_data["features"]
            bb_width = df[f"BBB_{self.config.bb_length}_{self.config.bb_std}"].iloc[-1]
            return Decimal(bb_width / 200)
        else:
            return Decimal("1.0")

    def get_executor_config(self, trade_type: TradeType, price: Decimal, amount: Decimal) -> DCAExecutorConfig:
        spread, amounts_quote = self.config.get_spreads_and_amounts_in_quote(trade_type, amount * price)
        spread_multiplier = self.get_spread_multiplier()
        if trade_type == TradeType.BUY:
            prices = [price * (1 - spread * spread_multiplier) for spread in spread]
        else:
            prices = [price * (1 + spread * spread_multiplier) for spread in spread]
        if self.config.dynamic_target:
            stop_loss = self.config.stop_loss * spread_multiplier
            trailing_stop = TrailingStop(activation_price=self.config.trailing_stop.activation_price * spread_multiplier,
                                         trailing_delta=self.config.trailing_stop.trailing_delta * spread_multiplier)
        else:
            stop_loss = self.config.stop_loss
            trailing_stop = self.config.trailing_stop
        return DCAExecutorConfig(
            timestamp=time.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            side=trade_type,
            mode=DCAMode.MAKER,
            prices=prices,
            amounts_quote=amounts_quote,
            time_limit=self.config.time_limit,
            stop_loss=stop_loss,
            trailing_stop=trailing_stop,
            leverage=self.config.leverage,
            activation_bounds=self.config.activation_bounds,
        )
