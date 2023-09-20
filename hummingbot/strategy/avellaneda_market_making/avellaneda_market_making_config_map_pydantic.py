from datetime import datetime, time
from decimal import Decimal
from typing import Dict, Optional, Union

from pydantic import Field, root_validator, validator

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_datetime_iso_string,
    validate_decimal,
    validate_int,
    validate_time_iso_string,
)
from hummingbot.client.config.strategy_config_data_types import BaseTradingStrategyConfigMap
from hummingbot.client.settings import required_exchanges
from hummingbot.connector.utils import split_hb_trading_pair


class InfiniteModel(BaseClientModel):
    class Config:
        title = "infinite"


class FromDateToDateModel(BaseClientModel):
    start_datetime: datetime = Field(
        default=...,
        description="The start date and time for date-to-date execution timeframe.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Please enter the start date and time (YYYY-MM-DD HH:MM:SS)",
            prompt_on_new=True,
        ),
    )
    end_datetime: datetime = Field(
        default=...,
        description="The end date and time for date-to-date execution timeframe.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Please enter the end date and time (YYYY-MM-DD HH:MM:SS)",
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "from_date_to_date"

    @validator("start_datetime", "end_datetime", pre=True)
    def validate_execution_time(cls, v: Union[str, datetime]) -> Optional[str]:
        if not isinstance(v, str):
            v = v.strftime("%Y-%m-%d %H:%M:%S")
        ret = validate_datetime_iso_string(v)
        if ret is not None:
            raise ValueError(ret)
        return v


class DailyBetweenTimesModel(BaseClientModel):
    start_time: time = Field(
        default=...,
        description="The start time for daily-between-times execution timeframe.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Please enter the start time (HH:MM:SS)",
            prompt_on_new=True,
        ),
    )
    end_time: time = Field(
        default=...,
        description="The end time for daily-between-times execution timeframe.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Please enter the end time (HH:MM:SS)",
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "daily_between_times"

    @validator("start_time", "end_time", pre=True)
    def validate_execution_time(cls, v: Union[str, datetime]) -> Optional[str]:
        if not isinstance(v, str):
            v = v.strftime("%H:%M:%S")
        ret = validate_time_iso_string(v)
        if ret is not None:
            raise ValueError(ret)
        return v


EXECUTION_TIMEFRAME_MODELS = {
    InfiniteModel.Config.title: InfiniteModel,
    FromDateToDateModel.Config.title: FromDateToDateModel,
    DailyBetweenTimesModel.Config.title: DailyBetweenTimesModel,
}


class SingleOrderLevelModel(BaseClientModel):
    class Config:
        title = "single_order_level"


class MultiOrderLevelModel(BaseClientModel):
    order_levels: int = Field(
        default=2,
        description="The number of orders placed on either side of the order book.",
        ge=2,
        client_data=ClientFieldData(
            prompt=lambda mi: "How many orders do you want to place on both sides?",
            prompt_on_new=True,
        ),
    )
    level_distances: Decimal = Field(
        default=Decimal("0"),
        description="The spread between order levels, expressed in % of optimal spread.",
        ge=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "How far apart in % of optimal spread should orders on one side be?",
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "multi_order_level"

    @validator("order_levels", pre=True)
    def validate_int_zero_or_above(cls, v: str):
        ret = validate_int(v, min_value=2)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("level_distances", pre=True)
    def validate_decimal_zero_or_above(cls, v: str):
        ret = validate_decimal(v, min_value=Decimal("0"), inclusive=True)
        if ret is not None:
            raise ValueError(ret)
        return v


ORDER_LEVEL_MODELS = {
    SingleOrderLevelModel.Config.title: SingleOrderLevelModel,
    MultiOrderLevelModel.Config.title: MultiOrderLevelModel,
}


class TrackHangingOrdersModel(BaseClientModel):
    hanging_orders_cancel_pct: Decimal = Field(
        default=Decimal("10"),
        description="The spread percentage at which hanging orders will be cancelled.",
        gt=0,
        lt=100,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "At what spread percentage (from mid price) will hanging orders be canceled?"
                " (Enter 1 to indicate 1%)"
            ),
        )
    )

    class Config:
        title = "track_hanging_orders"

    @validator("hanging_orders_cancel_pct", pre=True)
    def validate_pct_exclusive(cls, v: str):
        ret = validate_decimal(v, min_value=Decimal("0"), max_value=Decimal("100"), inclusive=False)
        if ret is not None:
            raise ValueError(ret)
        return v


class IgnoreHangingOrdersModel(BaseClientModel):
    class Config:
        title = "ignore_hanging_orders"


HANGING_ORDER_MODELS = {
    TrackHangingOrdersModel.Config.title: TrackHangingOrdersModel,
    IgnoreHangingOrdersModel.Config.title: IgnoreHangingOrdersModel,
}


class AvellanedaMarketMakingConfigMap(BaseTradingStrategyConfigMap):
    strategy: str = Field(default="avellaneda_market_making", client_data=None)
    execution_timeframe_mode: Union[InfiniteModel, FromDateToDateModel, DailyBetweenTimesModel] = Field(
        default=...,
        description="The execution timeframe.",
        client_data=ClientFieldData(
            prompt=lambda mi: f"Select the execution timeframe ({'/'.join(EXECUTION_TIMEFRAME_MODELS.keys())})",
            prompt_on_new=True,
        ),
    )
    order_amount: Decimal = Field(
        default=...,
        description="The strategy order amount.",
        gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: AvellanedaMarketMakingConfigMap.order_amount_prompt(mi),
            prompt_on_new=True,
        )
    )
    order_optimization_enabled: bool = Field(
        default=True,
        description=(
            "Allows the bid and ask order prices to be adjusted based on"
            " the current top bid and ask prices in the market."
        ),
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to enable best bid ask jumping? (Yes/No)"
        ),
    )
    risk_factor: Decimal = Field(
        default=Decimal("1"),
        description="The risk factor (\u03B3).",
        gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter risk factor (\u03B3)",
            prompt_on_new=True,
        ),
    )
    order_amount_shape_factor: Decimal = Field(
        default=Decimal("0"),
        description="The amount shape factor (\u03b7)",
        ge=0,
        le=1,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter order amount shape factor (\u03B7)",
        ),
    )
    min_spread: Decimal = Field(
        default=Decimal("0"),
        description="The minimum spread limit as percentage of the mid price.",
        ge=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter minimum spread limit (as % of mid price)",
        ),
    )
    order_refresh_time: float = Field(
        default=...,
        description="The frequency at which the orders' spreads will be re-evaluated.",
        gt=0.,
        client_data=ClientFieldData(
            prompt=lambda mi: "How often do you want to cancel and replace bids and asks (in seconds)?",
            prompt_on_new=True,
        ),
    )
    max_order_age: float = Field(
        default=1800.,
        description="A given order's maximum lifetime irrespective of spread.",
        gt=0.,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "How long do you want to cancel and replace bids and asks with the same price (in seconds)?"
            ),
        ),
    )
    order_refresh_tolerance_pct: Decimal = Field(
        default=Decimal("0"),
        description=(
            "The range of spreads tolerated on refresh cycles."
            " Orders over that range are cancelled and re-submitted."
        ),
        ge=-10,
        le=10,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "Enter the percent change in price needed to refresh orders at each cycle"
                " (Enter 1 to indicate 1%)"
            )
        ),
    )
    filled_order_delay: float = Field(
        default=60.,
        description="The delay before placing a new order after an order fill.",
        gt=0.,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "How long do you want to wait before placing the next order"
                " if your order gets filled (in seconds)?"
            )
        ),
    )
    inventory_target_base_pct: Decimal = Field(
        default=Decimal("50"),
        description="Defines the inventory target for the base asset.",
        ge=0,
        le=100,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is the inventory target for the base asset? Enter 50 for 50%",
            prompt_on_new=True,
        ),
    )
    add_transaction_costs: bool = Field(
        default=False,
        description="If activated, transaction costs will be added to order prices.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to add transaction costs automatically to order prices? (Yes/No)",
        ),
    )
    volatility_buffer_size: int = Field(
        default=200,
        description="The number of ticks that will be stored to calculate volatility.",
        ge=1,
        le=10_000,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter amount of ticks that will be stored to estimate order book liquidity",
        ),
    )
    trading_intensity_buffer_size: int = Field(
        default=200,
        description="The number of ticks that will be stored to calculate order book liquidity.",
        ge=1,
        le=10_000,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter amount of ticks that will be stored to estimate order book liquidity",
        ),
    )
    order_levels_mode: Union[SingleOrderLevelModel, MultiOrderLevelModel] = Field(
        default=SingleOrderLevelModel.construct(),
        description="Allows activating multi-order levels.",
        client_data=ClientFieldData(
            prompt=lambda mi: f"Select the order levels mode ({'/'.join(list(ORDER_LEVEL_MODELS.keys()))})",
        ),
    )
    order_override: Optional[Dict] = Field(
        default=None,
        description="Allows custom specification of the order levels and their spreads and amounts.",
        client_data=None,
    )
    hanging_orders_mode: Union[IgnoreHangingOrdersModel, TrackHangingOrdersModel] = Field(
        default=IgnoreHangingOrdersModel(),
        description="When tracking hanging orders, the orders on the side opposite to the filled orders remain active.",
        client_data=ClientFieldData(
            prompt=(
                lambda mi: f"How do you want to handle hanging orders? ({'/'.join(list(HANGING_ORDER_MODELS.keys()))})"
            ),
        ),
    )
    should_wait_order_cancel_confirmation: bool = Field(
        default=True,
        description=(
            "If activated, the strategy will await cancellation confirmation from the exchange"
            " before placing a new order."
        ),
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "Should the strategy wait to receive a confirmation for orders cancellation"
                " before creating a new set of orders?"
                " (Not waiting requires enough available balance) (Yes/No)"
            ),
        )
    )

    class Config:
        title = "avellaneda_market_making"

    # === prompts ===

    @classmethod
    def order_amount_prompt(cls, model_instance: 'AvellanedaMarketMakingConfigMap') -> str:
        trading_pair = model_instance.market
        base_asset, quote_asset = split_hb_trading_pair(trading_pair)
        return f"What is the amount of {base_asset} per order?"

    # === specific validations ===

    @validator("execution_timeframe_mode", pre=True)
    def validate_execution_timeframe(
        cls, v: Union[str, InfiniteModel, FromDateToDateModel, DailyBetweenTimesModel]
    ):
        if isinstance(v, (InfiniteModel, FromDateToDateModel, DailyBetweenTimesModel, Dict)):
            sub_model = v
        elif v not in EXECUTION_TIMEFRAME_MODELS:
            raise ValueError(
                f"Invalid timeframe, please choose value from {list(EXECUTION_TIMEFRAME_MODELS.keys())}"
            )
        else:
            sub_model = EXECUTION_TIMEFRAME_MODELS[v].construct()
        return sub_model

    @validator("order_refresh_tolerance_pct", pre=True)
    def validate_order_refresh_tolerance_pct(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_decimal(v, min_value=Decimal("-10"), max_value=Decimal("10"), inclusive=True)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("volatility_buffer_size", "trading_intensity_buffer_size", pre=True)
    def validate_buffer_size(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_int(v, 1, 10_000)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("order_levels_mode", pre=True)
    def validate_order_levels_mode(cls, v: Union[str, SingleOrderLevelModel, MultiOrderLevelModel]):
        if isinstance(v, (SingleOrderLevelModel, MultiOrderLevelModel, Dict)):
            sub_model = v
        elif v not in ORDER_LEVEL_MODELS:
            raise ValueError(
                f"Invalid order levels mode, please choose value from {list(ORDER_LEVEL_MODELS.keys())}."
            )
        else:
            sub_model = ORDER_LEVEL_MODELS[v].construct()
        return sub_model

    @validator("hanging_orders_mode", pre=True)
    def validate_hanging_orders_mode(cls, v: Union[str, IgnoreHangingOrdersModel, TrackHangingOrdersModel]):
        if isinstance(v, (TrackHangingOrdersModel, IgnoreHangingOrdersModel, Dict)):
            sub_model = v
        elif v not in HANGING_ORDER_MODELS:
            raise ValueError(
                f"Invalid hanging order mode, please choose value from {list(HANGING_ORDER_MODELS.keys())}."
            )
        else:
            sub_model = HANGING_ORDER_MODELS[v].construct()
        return sub_model

    # === generic validations ===

    @validator(
        "order_optimization_enabled",
        "add_transaction_costs",
        "should_wait_order_cancel_confirmation",
        pre=True,
    )
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v

    @validator("order_amount_shape_factor", pre=True)
    def validate_decimal_from_zero_to_one(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_decimal(v, min_value=Decimal("0"), max_value=Decimal("1"), inclusive=True)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator(
        "order_amount",
        "risk_factor",
        "order_refresh_time",
        "max_order_age",
        "filled_order_delay",
        pre=True,
    )
    def validate_decimal_above_zero(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_decimal(v, min_value=Decimal("0"), inclusive=False)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("min_spread", pre=True)
    def validate_decimal_zero_or_above(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_decimal(v, min_value=Decimal("0"), inclusive=True)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("inventory_target_base_pct", pre=True)
    def validate_pct_inclusive(cls, v: str):
        """Used for client-friendly error output."""
        ret = validate_decimal(v, min_value=Decimal("0"), max_value=Decimal("100"), inclusive=True)
        if ret is not None:
            raise ValueError(ret)
        return v

    # === post-validations ===

    @root_validator(skip_on_failure=True)
    def post_validations(cls, values: Dict):
        cls.exchange_post_validation(values)
        return values

    @classmethod
    def exchange_post_validation(cls, values: Dict):
        required_exchanges.add(values["exchange"])
