from decimal import Decimal
from typing import List, Optional

import pandas as pd
from pydantic import Field, field_validator

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TrailingStop,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class DirectionalTradingControllerConfigBase(ControllerConfigBase):
    """
    This class represents the configuration required to run a Directional Strategy.
    """
    controller_type: str = "directional_trading"
    connector_name: str = Field(
        default="binance_perpetual",
        json_schema_extra={
            "prompt": "Enter the connector name (e.g., binance_perpetual): ",
            "prompt_on_new": True}
    )
    trading_pair: str = Field(
        default="WLD-USDT",
        json_schema_extra={
            "prompt": "Enter the trading pair to trade on (e.g., WLD-USDT): ",
            "prompt_on_new": True}
    )
    max_executors_per_side: int = Field(
        default=2,
        json_schema_extra={
            "prompt": "Enter the maximum number of executors per side (e.g., 2): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    cooldown_time: int = Field(
        default=60 * 5, gt=0,
        json_schema_extra={
            "prompt": "Enter the cooldown time in seconds after executing a signal (e.g., 300 for 5 minutes): ",
            "prompt_on_new": True, "is_updatable": True},
    )
    leverage: int = Field(
        default=20,
        json_schema_extra={
            "prompt": "Enter the leverage to use for trading (e.g., 20 for 20x leverage). Set it to 1 for spot trading: ",
            "prompt_on_new": True}
    )
    position_mode: PositionMode = Field(
        default="HEDGE",
        json_schema_extra={"prompt": "Enter the position mode (HEDGE/ONEWAY): "}
    )
    # Triple Barrier Configuration
    stop_loss: Optional[Decimal] = Field(
        default=Decimal("0.03"), gt=0,
        json_schema_extra={
            "prompt": "Enter the stop loss (as a decimal, e.g., 0.03 for 3%): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    take_profit: Optional[Decimal] = Field(
        default=Decimal("0.02"), gt=0,
        json_schema_extra={
            "prompt": "Enter the take profit (as a decimal, e.g., 0.02 for 2%): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    time_limit: Optional[int] = Field(
        default=60 * 45, gt=0,
        json_schema_extra={
            "prompt": "Enter the time limit in seconds (e.g., 2700 for 45 minutes): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    take_profit_order_type: OrderType = Field(
        default=OrderType.LIMIT,
        json_schema_extra={
            "prompt": "Enter the order type for take profit (LIMIT/MARKET): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    trailing_stop: Optional[TrailingStop] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trailing stop as activation_price,trailing_delta (e.g., 0.015,0.003): ",
            "prompt_on_new": True, "is_updatable": True},
    )

    @field_validator("trailing_stop", mode="before")
    @classmethod
    def parse_trailing_stop(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
            activation_price, trailing_delta = v.split(",")
            return TrailingStop(activation_price=Decimal(activation_price), trailing_delta=Decimal(trailing_delta))
        return v

    @field_validator("time_limit", "stop_loss", "take_profit", mode="before")
    @classmethod
    def validate_target(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
            return Decimal(v)
        return v

    @field_validator('take_profit_order_type', mode="before")
    @classmethod
    def validate_order_type(cls, v) -> OrderType:
        if isinstance(v, OrderType):
            return v
        elif v is None:
            return OrderType.MARKET
        elif isinstance(v, str):
            cleaned_str = v.replace("OrderType.", "").upper()
            if cleaned_str in OrderType.__members__:
                return OrderType[cleaned_str]
        elif isinstance(v, int):
            try:
                return OrderType(v)
            except ValueError:
                pass
        raise ValueError(f"Invalid order type: {v}. Valid options are: {', '.join(OrderType.__members__)}")

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v: str) -> PositionMode:
        if isinstance(v, str):
            if v.upper() in PositionMode.__members__:
                return PositionMode[v.upper()]
            raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")
        return v

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            trailing_stop=self.trailing_stop,
            open_order_type=OrderType.MARKET,  # Defaulting to MARKET as is a Taker Controller
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,  # Defaulting to MARKET as per requirement
            time_limit_order_type=OrderType.MARKET  # Defaulting to MARKET as per requirement
        )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class DirectionalTradingControllerBase(ControllerBase):
    """
    This class represents the base class for a Directional Strategy.
    """

    def __init__(self, config: DirectionalTradingControllerConfigBase, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.market_data_provider.initialize_rate_sources([ConnectorPair(
            connector_name=config.connector_name, trading_pair=config.trading_pair)])

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the provided executor handler report.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    async def update_processed_data(self):
        """
        Update the processed data based on the current state of the strategy. Default signal 0
        """
        self.processed_data = {"signal": 0, "features": pd.DataFrame()}

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions based on the provided executor handler report.
        """
        create_actions = []
        signal = self.processed_data["signal"]
        if signal != 0 and self.can_create_executor(signal):
            price = self.market_data_provider.get_price_by_type(self.config.connector_name, self.config.trading_pair,
                                                                PriceType.MidPrice)
            # Default implementation distribute the total amount equally among the executors
            amount = self.config.total_amount_quote / price / Decimal(self.config.max_executors_per_side)
            trade_type = TradeType.BUY if signal > 0 else TradeType.SELL
            create_actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=self.get_executor_config(trade_type, price, amount)))

        return create_actions

    def can_create_executor(self, signal: int) -> bool:
        """
        Check if an executor can be created based on the signal, the quantity of active executors and the cooldown time.
        """
        active_executors_by_signal_side = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.is_active and (x.side == TradeType.BUY if signal > 0 else TradeType.SELL))
        max_timestamp = max([executor.timestamp for executor in active_executors_by_signal_side], default=0)
        active_executors_condition = len(active_executors_by_signal_side) < self.config.max_executors_per_side
        cooldown_condition = self.market_data_provider.time() - max_timestamp > self.config.cooldown_time
        return active_executors_condition and cooldown_condition

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Stop actions based on the provided executor handler report.
        """
        stop_actions = []
        return stop_actions

    def get_executor_config(self, trade_type: TradeType, price: Decimal, amount: Decimal):
        """
        Get the executor config based on the trade_type, price and amount. This method can be overridden by the
        subclasses if required.
        """
        return PositionExecutorConfig(
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
        return [format_df_for_printout(df.tail(5), table_format="psql",)]
