from typing import Any, Dict, List, Optional

from coinbase.rest.types.base_response import BaseResponse


# Create Order
class CreateOrderResponse(BaseResponse):
    def __init__(self, response: dict):
        if "success" in response:
            self.success: bool = response.pop("success")
        if "failure_reason" in response:
            self.failure_reason: Optional[Dict[str, Any]] = response.pop(
                "failure_reason"
            )
        if "order_id" in response:
            self.order_id: Optional[str] = response.pop("order_id")
        if "success_response" in response:
            self.success_response: Optional[CreateOrderSuccess] = response.pop(
                "success_response"
            )
        if "error_response" in response:
            self.error_response: Optional[CreateOrderError] = response.pop(
                "error_response"
            )
        if "order_configuration" in response:
            self.order_configuration: Optional[OrderConfiguration] = OrderConfiguration(
                **response.pop("order_configuration")
            )
        super().__init__(**response)


# Cancel Orders
class CancelOrdersResponse(BaseResponse):
    def __init__(self, response: dict):
        if "results" in response:
            self.results: Optional[List[CancelOrderObject]] = [
                CancelOrderObject(**result) for result in response.pop("results")
            ]
        super().__init__(**response)


# Edit Order
class EditOrderResponse(BaseResponse):
    def __init__(self, response: dict):
        if "success" in response:
            self.success: bool = response.pop("success")
        if "success_response" in response:
            self.success_response: Optional[EditOrderSuccess] = response.pop(
                "success_response"
            )
        if "error_response" in response:
            self.error_response: Optional[EditOrderError] = response.pop(
                "error_response"
            )
        if "errors" in response:
            self.errors: Optional[List[EditOrderErrors]] = [
                EditOrderErrors(**error) for error in response.pop("errors")
            ]
        super().__init__(**response)


# Edit Order Preview
class EditOrderPreviewResponse(BaseResponse):
    def __init__(self, response: dict):
        if "errors" in response:
            self.errors: List[EditOrderErrors] = [
                EditOrderErrors(**error) for error in response.pop("errors")
            ]
        if "slippage" in response:
            self.slippage: Optional[str] = response.pop("slippage")
        if "order_total" in response:
            self.order_total: Optional[str] = response.pop("order_total")
        if "commission_total" in response:
            self.commission_total: Optional[str] = response.pop("commission_total")
        if "quote_size" in response:
            self.quote_size: Optional[str] = response.pop("quote_size")
        if "base_size" in response:
            self.base_size: Optional[str] = response.pop("base_size")
        if "best_bid" in response:
            self.best_bid: Optional[str] = response.pop("best_bid")
        if "average_filled_price" in response:
            self.average_filled_price: Optional[str] = response.pop(
                "average_filled_price"
            )
        super().__init__(**response)


# List Orders
class ListOrdersResponse(BaseResponse):
    def __init__(self, response: dict):
        if "orders" in response:
            self.orders: List[Order] = [
                Order(**order) for order in response.pop("orders")
            ]
        if "sequence" in response:
            self.sequence: Optional[int] = response.pop("sequence")
        if "has_next" in response:
            self.has_next: bool = response.pop("has_next")
        if "cursor" in response:
            self.cursor: Optional[str] = response.pop("cursor")
        super().__init__(**response)


# List Fills
class ListFillsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "fills" in response:
            self.fills: Optional[List[Fill]] = [
                Fill(**fill) for fill in response.pop("fills")
            ]
        if "cursor" in response:
            self.cursor: Optional[str] = response.pop("cursor")
        super().__init__(**response)


# Get Order
class GetOrderResponse(BaseResponse):
    def __init__(self, response: dict):
        if "order" in response:
            self.order: Optional[Order] = Order(**response.pop("order"))
        super().__init__(**response)


# Preview Order
class PreviewOrderResponse(BaseResponse):
    def __init__(self, response: dict):
        if "order_total" in response:
            self.order_total: str = response.pop("order_total")
        if "commission_total" in response:
            self.commission_total: str = response.pop("commission_total")
        if "errs" in response:
            self.errs: List[Dict[str, Any]] = response.pop("errs")
        if "warning" in response:
            self.warning: List[Dict[str, Any]] = response.pop("warning")
        if "quote_size" in response:
            self.quote_size: str = response.pop("quote_size")
        if "base_size" in response:
            self.base_size: str = response.pop("base_size")
        if "best_bid" in response:
            self.best_bid: str = response.pop("best_bid")
        if "best_ask" in response:
            self.best_ask: str = response.pop("best_ask")
        if "is_max" in response:
            self.is_max: bool = response.pop("is_max")
        if "order_margin_total" in response:
            self.order_margin_total: Optional[str] = response.pop("order_margin_total")
        if "leverage" in response:
            self.leverage: Optional[str] = response.pop("leverage")
        if "long_leverage" in response:
            self.long_leverage: Optional[str] = response.pop("long_leverage")
        if "short_leverage" in response:
            self.short_leverage: Optional[str] = response.pop("short_leverage")
        if "slippage" in response:
            self.slippage: Optional[str] = response.pop("slippage")
        if "preview_id" in response:
            self.preview_id: Optional[str] = response.pop("preview_id")
        if "current_liquidation_buffer" in response:
            self.current_liquidation_buffer: Optional[str] = response.pop(
                "current_liquidation_buffer"
            )
        if "projected_liquidation_buffer" in response:
            self.projected_liquidation_buffer: Optional[str] = response.pop(
                "projected_liquidation_buffer"
            )
        if "max_leverage" in response:
            self.max_leverage: Optional[str] = response.pop("max_leverage")
        if "pnl_configuration" in response:
            self.pnl_configuration: Optional[Dict[str, Any]] = response.pop(
                "pnl_configuration"
            )
        super().__init__(**response)


# Close Position
class ClosePositionResponse(BaseResponse):
    def __init__(self, response: dict):
        if "success" in response:
            self.success: bool = response.pop("success")
        if "success_response" in response:
            self.success_response: Optional[CreateOrderSuccess] = response.pop(
                "success_response"
            )
        if "error_response" in response:
            self.error_response: Optional[CreateOrderError] = response.pop(
                "error_response"
            )
        if "order_configuration" in response:
            self.order_configuration: Optional[OrderConfiguration] = OrderConfiguration(
                **response.pop("order_configuration")
            )
        super().__init__(**response)


# ----------------------------------------------------------------


class OrderConfiguration(BaseResponse):
    def __init__(self, **kwargs):
        if "market_market_ioc" in kwargs:
            self.market_market_ioc: Optional[MarketMarketIoc] = MarketMarketIoc(
                **kwargs.pop("market_market_ioc")
            )
        if "sor_limit_ioc" in kwargs:
            self.sor_limit_ioc: Optional[SorLimitIoc] = SorLimitIoc(
                **kwargs.pop("sor_limit_ioc")
            )
        if "limit_limit_gtc" in kwargs:
            self.limit_limit_gtc: Optional[LimitLimitGtc] = LimitLimitGtc(
                **kwargs.pop("limit_limit_gtc")
            )
        if "limit_limit_gtd" in kwargs:
            self.limit_limit_gtd: Optional[LimitLimitGtd] = LimitLimitGtd(
                **kwargs.pop("limit_limit_gtd")
            )
        if "limit_limit_fok" in kwargs:
            self.limit_limit_fok: Optional[LimitLimitFok] = LimitLimitFok(
                **kwargs.pop("limit_limit_fok")
            )
        if "stop_limit_stop_limit_gtc" in kwargs:
            self.stop_limit_stop_limit_gtc: Optional[StopLimitStopLimitGtc] = (
                StopLimitStopLimitGtc(**kwargs.pop("stop_limit_stop_limit_gtc"))
            )
        if "stop_limit_stop_limit_gtd" in kwargs:
            self.stop_limit_stop_limit_gtd: Optional[StopLimitStopLimitGtd] = (
                StopLimitStopLimitGtd(**kwargs.pop("stop_limit_stop_limit_gtd"))
            )
        if "trigger_bracket_gtc" in kwargs:
            self.trigger_bracket_gtc: Optional[TriggerBracketGtc] = TriggerBracketGtc(
                **kwargs.pop("trigger_bracket_gtc")
            )

        if "trigger_bracket_gtd" in kwargs:
            self.trigger_bracket_gtd: Optional[TriggerBracketGtd] = TriggerBracketGtd(
                **kwargs.pop("trigger_bracket_gtd")
            )
        super().__init__(**kwargs)


class MarketMarketIoc(BaseResponse):
    def __init__(self, **kwargs):
        if "quote_size" in kwargs:
            self.quote_size: str = kwargs.pop("quote_size")
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        super().__init__(**kwargs)


class SorLimitIoc(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        super().__init__(**kwargs)


class LimitLimitGtc(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        if "post_only" in kwargs:
            self.post_only: bool = kwargs.pop("post_only")
        super().__init__(**kwargs)


class LimitLimitGtd(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        if "end_time" in kwargs:
            self.end_time: str = kwargs.pop("end_time")
        if "post_only" in kwargs:
            self.post_only: bool = kwargs.pop("post_only")
        super().__init__(**kwargs)


class LimitLimitFok(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        super().__init__(**kwargs)


class StopLimitStopLimitGtc(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        if "stop_price" in kwargs:
            self.stop_price: str = kwargs.pop("stop_price")
        if "stop_direction" in kwargs:
            self.stop_direction: str = kwargs.pop("stop_direction")
        super().__init__(**kwargs)


class StopLimitStopLimitGtd(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        if "stop_price" in kwargs:
            self.stop_price: str = kwargs.pop("stop_price")
        if "end_time" in kwargs:
            self.end_time: str = kwargs.pop("end_time")
        if "stop_direction" in kwargs:
            self.stop_direction: str = kwargs.pop("stop_direction")

        super().__init__(**kwargs)


class TriggerBracketGtc(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        if "stop_trigger_price" in kwargs:
            self.stop_trigger_price: str = kwargs.pop("stop_trigger_price")
        super().__init__(**kwargs)


class TriggerBracketGtd(BaseResponse):
    def __init__(self, **kwargs):
        if "base_size" in kwargs:
            self.base_size: str = kwargs.pop("base_size")
        if "limit_price" in kwargs:
            self.limit_price: str = kwargs.pop("limit_price")
        if "stop_trigger_price" in kwargs:
            self.stop_trigger_price: str = kwargs.pop("stop_trigger_price")
        if "end_time" in kwargs:
            self.end_time: str = kwargs.pop("end_time")
        super().__init__(**kwargs)


class Order(BaseResponse):
    def __init__(self, **kwargs):
        if "order_id" in kwargs:
            self.order_id: str = kwargs.pop("order_id")
        if "product_id" in kwargs:
            self.product_id: str = kwargs.pop("product_id")
        if "user_id" in kwargs:
            self.user_id: str = kwargs.pop("user_id")
        if "order_configuration" in kwargs:
            self.order_configuration: OrderConfiguration = OrderConfiguration(
                **kwargs.pop("order_configuration")
            )
        if "side" in kwargs:
            self.side: str = kwargs.pop("side")
        if "client_order_id" in kwargs:
            self.client_order_id: str = kwargs.pop("client_order_id")
        if "status" in kwargs:
            self.status: str = kwargs.pop("status")
        if "time_in_force" in kwargs:
            self.time_in_force: Optional[str] = kwargs.pop("time_in_force")
        if "created_time" in kwargs:
            self.created_time: str = kwargs.pop("created_time")
        if "completion_percentage" in kwargs:
            self.completion_percentage: str = kwargs.pop("completion_percentage")
        if "filled_size" in kwargs:
            self.filled_size: Optional[str] = kwargs.pop("filled_size")
        if "average_filled_price" in kwargs:
            self.average_filled_price: str = kwargs.pop("average_filled_price")
        if "fee" in kwargs:
            self.fee: Optional[str] = kwargs.pop("fee")
        if "number_of_fills" in kwargs:
            self.number_of_fills: str = kwargs.pop("number_of_fills")
        if "filled_value" in kwargs:
            self.filled_value: Optional[str] = kwargs.pop("filled_value")
        if "pending_cancel" in kwargs:
            self.pending_cancel: bool = kwargs.pop("pending_cancel")
        if "size_in_quote" in kwargs:
            self.size_in_quote: bool = kwargs.pop("size_in_quote")
        if "total_fees" in kwargs:
            self.total_fees: str = kwargs.pop("total_fees")
        if "size_inclusive_of_fees" in kwargs:
            self.size_inclusive_of_fees: bool = kwargs.pop("size_inclusive_of_fees")
        if "total_value_after_fees" in kwargs:
            self.total_value_after_fees: str = kwargs.pop("total_value_after_fees")
        if "trigger_status" in kwargs:
            self.trigger_status: Optional[str] = kwargs.pop("trigger_status")
        if "order_type" in kwargs:
            self.order_type: Optional[str] = kwargs.pop("order_type")
        if "reject_reason" in kwargs:
            self.reject_reason: Optional[str] = kwargs.pop("reject_reason")
        if "settled" in kwargs:
            self.settled: Optional[bool] = kwargs.pop("settled")
        if "product_type" in kwargs:
            self.product_type: Optional[str] = kwargs.pop("product_type")
        if "reject_message" in kwargs:
            self.reject_message: Optional[str] = kwargs.pop("reject_message")
        if "cancel_message" in kwargs:
            self.cancel_message: Optional[str] = kwargs.pop("cancel_message")
        if "order_placement_source" in kwargs:
            self.order_placement_source: Optional[str] = kwargs.pop(
                "order_placement_source"
            )
        if "outstanding_hold_amount" in kwargs:
            self.outstanding_hold_amount: Optional[str] = kwargs.pop(
                "outstanding_hold_amount"
            )
        if "is_liquidation" in kwargs:
            self.is_liquidation: Optional[bool] = kwargs.pop("is_liquidation")
        if "last_fill_time" in kwargs:
            self.last_fill_time: Optional[str] = kwargs.pop("last_fill_time")
        if "edit_history" in kwargs:
            self.edit_history: Optional[List[EditHistory]] = [
                EditHistory(**edit) for edit in kwargs.pop("edit_history")
            ]
        if "leverage" in kwargs:
            self.leverage: Optional[str] = kwargs.pop("leverage")
        if "margin_type" in kwargs:
            self.margin_type: Optional[str] = kwargs.pop("margin_type")
        if "retail_portfolio_id" in kwargs:
            self.retail_portfolio_id: Optional[str] = kwargs.pop("retail_portfolio_id")
        if "originating_order_id" in kwargs:
            self.originating_order_id: Optional[str] = kwargs.pop(
                "originating_order_id"
            )
        if "attached_order_id" in kwargs:
            self.attached_order_id: Optional[str] = kwargs.pop("attached_order_id")
        # NOT LIVE YET
        # if "attached_order_configuration" in kwargs:
        #     self.attached_order_configuration: Optional[
        #         OrderConfiguration
        #     ] = OrderConfiguration(**kwargs.pop("attached_order_configuration"))
        super().__init__(**kwargs)


class Fill(BaseResponse):
    def __init__(self, **kwargs):
        if "entry_id" in kwargs:
            self.entry_id: str = kwargs.pop("entry_id")
        if "trade_id" in kwargs:
            self.trade_id: str = kwargs.pop("trade_id")
        if "order_id" in kwargs:
            self.order_id: str = kwargs.pop("order_id")
        if "trade_time" in kwargs:
            self.trade_time: str = kwargs.pop("trade_time")
        if "trade_type" in kwargs:
            self.trade_type: str = kwargs.pop("trade_type")
        if "price" in kwargs:
            self.price: str = kwargs.pop("price")
        if "size" in kwargs:
            self.size: str = kwargs.pop("size")
        if "commission" in kwargs:
            self.commission: str = kwargs.pop("commission")
        if "product_id" in kwargs:
            self.product_id: str = kwargs.pop("product_id")
        if "sequence_timestamp" in kwargs:
            self.sequence_timestamp: str = kwargs.pop("sequence_timestamp")
        if "liquidity_indicator" in kwargs:
            self.liquidity_indicator: str = kwargs.pop("liquidity_indicator")
        if "size_in_quote" in kwargs:
            self.size_in_quote: str = kwargs.pop("size_in_quote")
        if "user_id" in kwargs:
            self.user_id: str = kwargs.pop("user_id")
        if "user_id" in kwargs:
            self.user_id: str = kwargs.pop("user_id")
        if "side" in kwargs:
            self.side: str = kwargs.pop("side")
        if "retail_portfolio_id" in kwargs:
            self.retail_portfolio_id: str = kwargs.pop("retail_portfolio_id")
        super().__init__(**kwargs)


class EditHistory(BaseResponse):
    def __init__(self, **kwargs):
        if "price" in kwargs:
            self.price: Optional[str] = kwargs.pop("price")
        if "size" in kwargs:
            self.size: Optional[str] = kwargs.pop("size")
        if "replace_accept_timestamp" in kwargs:
            self.replace_accept_timestamp: Optional[str] = kwargs.pop(
                "replace_accept_timestamp"
            )
        super().__init__(**kwargs)


class CancelOrderObject(BaseResponse):
    def __init__(self, **kwargs):
        if "success" in kwargs:
            self.success: bool = kwargs.pop("success")
        if "failure_reason" in kwargs:
            self.failure_reason: str = kwargs.pop("failure_reason")
        if "order_id" in kwargs:
            self.order_id: str = kwargs.pop("order_id")
        super().__init__(**kwargs)


class CreateOrderSuccess(BaseResponse):
    def __init__(self, **kwargs):
        if "order_id" in kwargs:
            self.order_id: Optional[str] = kwargs.pop("order_id")
        if "product_id" in kwargs:
            self.product_id: Optional[str] = kwargs.pop("product_id")
        if "side" in kwargs:
            self.side: Optional[str] = kwargs.pop("side")
        if "client_order_id" in kwargs:
            self.client_order_id: Optional[str] = kwargs.pop("client_order_id")
        if "attached_order_id" in kwargs:
            self.attached_order_id: Optional[str] = kwargs.pop("attached_order_id")
        super().__init__(**kwargs)


class CreateOrderError(BaseResponse):
    def __init__(self, **kwargs):
        if "error" in kwargs:
            self.error: Optional[str] = kwargs.pop("error")
        if "message" in kwargs:
            self.message: Optional[str] = kwargs.pop("message")
        if "error_details" in kwargs:
            self.error_details: Optional[str] = kwargs.pop("error_details")
        if "preview_failure_reason" in kwargs:
            self.preview_failure_reason: Optional[str] = kwargs.pop(
                "preview_failure_reason"
            )
        if "new_order_failure_reason" in kwargs:
            self.new_order_failure_reason: Optional[str] = kwargs.pop(
                "new_order_failure_reason"
            )
        super().__init__(**kwargs)


class EditOrderSuccess(BaseResponse):
    def __init__(self, **kwargs):
        if "order_id" in kwargs:
            self.order_id: str = kwargs.pop("order_id")
        super().__init__(**kwargs)


class EditOrderError(BaseResponse):
    def __init__(self, **kwargs):
        if "error_details" in kwargs:
            self.error_details: Optional[str] = kwargs.pop("error_details")
        if "edit_order_failure_reason" in kwargs:
            self.edit_order_failure_reason: str = kwargs.pop(
                "edit_order_failure_reason"
            )
        super().__init__(**kwargs)


class EditOrderErrors(BaseResponse):
    def __init__(self, **kwargs):
        if "edit_failure_reason" in kwargs:
            self.edit_failure_reason: Optional[str] = kwargs.pop("edit_failure_reason")
        if "preview_failure_reason" in kwargs:
            self.preview_failure_reason: Optional[str] = kwargs.pop(
                "preview_failure_reason"
            )
        super().__init__(**kwargs)
