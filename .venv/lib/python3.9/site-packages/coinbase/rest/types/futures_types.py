from typing import Any, Dict, List, Optional

from coinbase.rest.types.base_response import BaseResponse
from coinbase.rest.types.common_types import Amount


# Get Futures Balance Summary
class GetFuturesBalanceSummaryResponse(BaseResponse):
    def __init__(self, response: dict):
        if "balance_summary" in response:
            self.balance_summary: Optional[FCMBalanceSummary] = FCMBalanceSummary(
                **response.pop("balance_summary")
            )
        super().__init__(**response)


# List Futures Positions
class ListFuturesPositionsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "positions" in response:
            self.positions: Optional[List[FCMPosition]] = [
                FCMPosition(**position) for position in response.pop("positions")
            ]
        super().__init__(**response)


# Get Futures Position
class GetFuturesPositionResponse(BaseResponse):
    def __init__(self, response: dict):
        if "position" in response:
            self.position: Optional[FCMPosition] = FCMPosition(
                **response.pop("position")
            )
        super().__init__(**response)


# Schedule Futures Sweep
class ScheduleFuturesSweepResponse(BaseResponse):
    def __init__(self, response: dict):
        if "success" in response:
            self.success: Optional[bool] = response.pop("success")
        super().__init__(**response)


# List Futures Sweeps
class ListFuturesSweepsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "sweeps" in response:
            self.sweeps: List[FCMSweep] = [
                FCMSweep(**sweep) for sweep in response.pop("sweeps")
            ]
        super().__init__(**response)


# Cancel Pending Futures Sweep
class CancelPendingFuturesSweepResponse(BaseResponse):
    def __init__(self, response: dict):
        if "success" in response:
            self.success: Optional[bool] = response.pop("success")
        super().__init__(**response)


# Get Intraday Margin Setting
class GetIntradayMarginSettingResponse(BaseResponse):
    def __init__(self, response: dict):
        if "setting" in response:
            self.setting: Optional[str] = response.pop("setting")
        super().__init__(**response)


# Get Current Margin Window
class GetCurrentMarginWindowResponse(BaseResponse):
    def __init__(self, response: dict):
        if "margin_window" in response:
            self.margin_window: Optional[MarginWindow] = response.pop("margin_window")
        if "is_intraday_margin_killswitch_enabled" in response:
            self.is_intraday_margin_killswitch_enabled: Optional[bool] = response.pop(
                "is_intraday_margin_killswitch_enabled"
            )
        if "is_intraday_margin_enrollment_killswitch_enabled" in response:
            self.is_intraday_margin_enrollment_killswitch_enabled: Optional[bool] = (
                response.pop("is_intraday_margin_enrollment_killswitch_enabled")
            )
        super().__init__(**response)


# Set Intraday Margin Setting
class SetIntradayMarginSettingResponse(BaseResponse):
    def __init__(self, response: dict):
        super().__init__(**response)


# ----------------------------------------------------------------


class FCMBalanceSummary(BaseResponse):
    def __init__(self, **kwargs):
        if "futures_buying_power" in kwargs:
            self.futures_buying_power: Optional[Amount] = kwargs.pop(
                "futures_buying_power"
            )
        if "total_usd_balance" in kwargs:
            self.total_usd_balance: Optional[Amount] = kwargs.pop("total_usd_balance")
        if "cbi_usd_balance" in kwargs:
            self.cbi_usd_balance: Optional[Amount] = kwargs.pop("cbi_usd_balance")
        if "cfm_usd_balance" in kwargs:
            self.cfm_usd_balance: Optional[Amount] = kwargs.pop("cfm_usd_balance")
        if "total_open_orders_hold_amount" in kwargs:
            self.total_open_orders_hold_amount: Optional[Amount] = kwargs.pop(
                "total_open_orders_hold_amount"
            )
        if "unrealized_pnl" in kwargs:
            self.unrealized_pnl: Optional[Amount] = kwargs.pop("unrealized_pnl")
        if "daily_realized_pnl" in kwargs:
            self.daily_realized_pnl: Optional[Amount] = kwargs.pop("daily_realized_pnl")
        if "initial_margin" in kwargs:
            self.initial_margin: Optional[Amount] = kwargs.pop("initial_margin")
        if "available_margin" in kwargs:
            self.available_margin: Optional[Amount] = kwargs.pop("available_margin")
        if "liquidation_threshold" in kwargs:
            self.liquidation_threshold: Optional[Amount] = kwargs.pop(
                "liquidation_threshold"
            )
        if "liquidation_buffer_amount" in kwargs:
            self.liquidation_buffer_amount: Optional[Amount] = kwargs.pop(
                "liquidation_buffer_amount"
            )
        if "liquidation_buffer_percentage" in kwargs:
            self.liquidation_buffer_percentage: Optional[str] = kwargs.pop(
                "liquidation_buffer_percentage"
            )
        if "intraday_margin_window_measure" in kwargs:
            self.intraday_margin_window_measure: Optional[Dict[str, Any]] = kwargs.pop(
                "intraday_margin_window_measure"
            )
        if "overnight_margin_window_measure" in kwargs:
            self.overnight_margin_window_measure: Optional[Dict[str, Any]] = kwargs.pop(
                "overnight_margin_window_measure"
            )
        super().__init__(**kwargs)


class FCMPosition(BaseResponse):
    def __init__(self, **kwargs):
        if "product_id" in kwargs:
            self.product_id: Optional[str] = kwargs.pop("product_id")
        if "expiration_time" in kwargs:
            self.expiration_time: Optional[Dict[str, Any]] = kwargs.pop(
                "expiration_time"
            )
        if "side" in kwargs:
            self.side: Optional[str] = kwargs.pop("side")
        if "number_of_contracts" in kwargs:
            self.number_of_contracts: Optional[str] = kwargs.pop("number_of_contracts")
        if "current_price" in kwargs:
            self.current_price: Optional[str] = kwargs.pop("current_price")
        if "avg_entry_price" in kwargs:
            self.avg_entry_price: Optional[str] = kwargs.pop("avg_entry_price")
        if "unrealized_pnl" in kwargs:
            self.unrealized_pnl: Optional[str] = kwargs.pop("unrealized_pnl")
        if "daily_realized_pnl" in kwargs:
            self.daily_realized_pnl: Optional[str] = kwargs.pop("daily_realized_pnl")
        super().__init__(**kwargs)


class MarginWindow(BaseResponse):
    def __init__(self, **kwargs):
        if "margin_window_type" in kwargs:
            self.margin_window_type: str = kwargs.pop("margin_window_type")
        if "end_time" in kwargs:
            self.end_time: str = kwargs.pop("end_time")
        super().__init__(**kwargs)


class FCMSweep(BaseResponse):
    def __init__(self, **kwargs):
        if "id" in kwargs:
            self.id: str = kwargs.pop("id")
        if "requested_amount" in kwargs:
            self.requested_amount: Amount = kwargs.pop("requested_amount")
        if "should_sweep_all" in kwargs:
            self.should_sweep_all: bool = kwargs.pop("should_sweep_all")
        if "status" in kwargs:
            self.status: str = kwargs.pop("status")
        if "schedule_time" in kwargs:
            self.schedule_time: Dict[str, Any] = kwargs.pop("schedule_time")

        super().__init__(**kwargs)
