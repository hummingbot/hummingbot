from typing import List, Optional

from coinbase.websocket.types.base_response import BaseResponse


class WSHeartBeats(BaseResponse):
    def __init__(self, **kwargs):
        self.current_time: Optional[str] = kwargs.pop("current_time", None)
        self.heartbeat_counter: Optional[str] = kwargs.pop("heartbeat_counter", None)
        super().__init__(**kwargs)


class WSCandle(BaseResponse):
    def __init__(self, **kwargs):
        self.start: Optional[str] = kwargs.pop("start", None)
        self.high: Optional[str] = kwargs.pop("high", None)
        self.low: Optional[str] = kwargs.pop("low", None)
        self.open: Optional[str] = kwargs.pop("open", None)
        self.close: Optional[str] = kwargs.pop("close", None)
        self.volume: Optional[str] = kwargs.pop("volume", None)
        self.product_id: Optional[str] = kwargs.pop("product_id", None)
        super().__init__(**kwargs)


class WSHistoricalMarketTrade(BaseResponse):
    def __init__(self, **kwargs):
        self.product_id: Optional[str] = kwargs.pop("product_id", None)
        self.trade_id: Optional[str] = kwargs.pop("trade_id", None)
        self.price: Optional[str] = kwargs.pop("price", None)
        self.size: Optional[str] = kwargs.pop("size", None)
        self.time: Optional[str] = kwargs.pop("time", None)
        self.side: Optional[str] = kwargs.pop("side", None)
        super().__init__(**kwargs)


class WSProduct(BaseResponse):
    def __init__(self, **kwargs):
        self.product_type: Optional[str] = kwargs.pop("product_type", None)
        self.id: Optional[str] = kwargs.pop("id", None)
        self.base_currency: Optional[str] = kwargs.pop("base_currency", None)
        self.quote_currency: Optional[str] = kwargs.pop("quote_currency", None)
        self.base_increment: Optional[str] = kwargs.pop("base_increment", None)
        self.quote_increment: Optional[str] = kwargs.pop("quote_increment", None)
        self.display_name: Optional[str] = kwargs.pop("display_name", None)
        self.status: Optional[str] = kwargs.pop("status", None)
        self.status_message: Optional[str] = kwargs.pop("status_message", None)
        self.min_market_funds: Optional[str] = kwargs.pop("min_market_funds", None)
        super().__init__(**kwargs)


class WSTicker(BaseResponse):
    def __init__(self, **kwargs):
        self.type: Optional[str] = kwargs.pop("type", None)
        self.product_id: Optional[str] = kwargs.pop("product_id", None)
        self.price: Optional[str] = kwargs.pop("price", None)
        self.volume_24_h: Optional[str] = kwargs.pop("volume_24_h", None)
        self.low_24_h: Optional[str] = kwargs.pop("low_24_h", None)
        self.high_24_h: Optional[str] = kwargs.pop("high_24_h", None)
        self.low_52_w: Optional[str] = kwargs.pop("low_52_w", None)
        self.high_52_w: Optional[str] = kwargs.pop("high_52_w", None)
        self.price_percent_chg_24_h: Optional[str] = kwargs.pop(
            "price_percent_chg_24_h", None
        )
        self.best_bid: Optional[str] = kwargs.pop("best_bid", None)
        self.best_ask: Optional[str] = kwargs.pop("best_ask", None)
        self.best_bid_quantity: Optional[str] = kwargs.pop("best_bid_quantity", None)
        self.best_ask_quantity: Optional[str] = kwargs.pop("best_ask_quantity", None)
        super().__init__(**kwargs)


class L2Update(BaseResponse):
    def __init__(self, **kwargs):
        self.side: Optional[str] = kwargs.pop("side", None)
        self.event_time: Optional[str] = kwargs.pop("event_time", None)
        self.price_level: Optional[str] = kwargs.pop("price_level", None)
        self.new_quantity: Optional[str] = kwargs.pop("new_quantity", None)
        super().__init__(**kwargs)


class UserOrders(BaseResponse):
    def __init__(self, **kwargs):
        self.avg_price: Optional[str] = kwargs.pop("avg_price", None)
        self.cancel_reason: Optional[str] = kwargs.pop("cancel_reason", None)
        self.client_order_id: Optional[str] = kwargs.pop("client_order_id", None)
        self.completion_percentage: Optional[str] = kwargs.pop(
            "completion_percentage", None
        )
        self.contract_expiry_type: Optional[str] = kwargs.pop(
            "contract_expiry_type", None
        )
        self.cumulative_quantity: Optional[str] = kwargs.pop(
            "cumulative_quantity", None
        )
        self.filled_value: Optional[str] = kwargs.pop("filled_value", None)
        self.leaves_quantity: Optional[str] = kwargs.pop("leaves_quantity", None)
        self.limit_price: Optional[str] = kwargs.pop("limit_price", None)
        self.number_of_fills: Optional[str] = kwargs.pop("number_of_fills", None)
        self.order_id: Optional[str] = kwargs.pop("order_id", None)
        self.order_side: Optional[str] = kwargs.pop("order_side", None)
        self.order_type: Optional[str] = kwargs.pop("order_type", None)
        self.outstanding_hold_amount: Optional[str] = kwargs.pop(
            "outstanding_hold_amount", None
        )
        self.post_only: Optional[str] = kwargs.pop("post_only", None)
        self.product_id: Optional[str] = kwargs.pop("product_id", None)
        self.product_type: Optional[str] = kwargs.pop("product_type", None)
        self.reject_reason: Optional[str] = kwargs.pop("reject_reason", None)
        self.retail_portfolio_id: Optional[str] = kwargs.pop(
            "retail_portfolio_id", None
        )
        self.risk_managed_by: Optional[str] = kwargs.pop("risk_managed_by", None)
        self.status: Optional[str] = kwargs.pop("status", None)
        self.stop_price: Optional[str] = kwargs.pop("stop_price", None)
        self.time_in_force: Optional[str] = kwargs.pop("time_in_force", None)
        self.total_fees: Optional[str] = kwargs.pop("total_fees", None)
        self.total_value_after_fees: Optional[str] = kwargs.pop(
            "total_value_after_fees", None
        )
        self.trigger_status: Optional[str] = kwargs.pop("trigger_status", None)
        self.creation_time: Optional[str] = kwargs.pop("creation_time", None)
        self.end_time: Optional[str] = kwargs.pop("end_time", None)
        self.start_time: Optional[str] = kwargs.pop("start_time", None)
        super().__init__(**kwargs)


class UserPositions(BaseResponse):
    def __init__(self, **kwargs):
        self.perpetual_futures_positions: Optional[List[UserFuturesPositions]] = (
            [
                UserFuturesPositions(**position)
                for position in kwargs.pop("perpetual_futures_positions", [])
            ]
            if kwargs.get("perpetual_futures_positions") is not None
            else []
        )
        self.expiring_futures_positions: Optional[List[UserExpFuturesPositions]] = (
            [
                UserExpFuturesPositions(**position)
                for position in kwargs.pop("expiring_futures_positions", [])
            ]
            if kwargs.get("expiring_futures_positions") is not None
            else []
        )
        super().__init__(**kwargs)


class UserFuturesPositions(BaseResponse):
    def __init__(self, **kwargs):
        self.product_id: Optional[str] = kwargs.pop("product_id", None)
        self.portfolio_uuid: Optional[str] = kwargs.pop("portfolio_uuid", None)
        self.vwap: Optional[str] = kwargs.pop("vwap", None)
        self.entry_vwap: Optional[str] = kwargs.pop("entry_vwap", None)
        self.position_side: Optional[str] = kwargs.pop("position_side", None)
        self.margin_type: Optional[str] = kwargs.pop("margin_type", None)
        self.net_size: Optional[str] = kwargs.pop("net_size", None)
        self.buy_order_size: Optional[str] = kwargs.pop("buy_order_size", None)
        self.sell_order_size: Optional[str] = kwargs.pop("sell_order_size", None)
        self.leverage: Optional[str] = kwargs.pop("leverage", None)
        self.mark_price: Optional[str] = kwargs.pop("mark_price", None)
        self.liquidation_price: Optional[str] = kwargs.pop("liquidation_price", None)
        self.im_notional: Optional[str] = kwargs.pop("im_notional", None)
        self.mm_notional: Optional[str] = kwargs.pop("mm_notional", None)
        self.position_notional: Optional[str] = kwargs.pop("position_notional", None)
        self.unrealized_pnl: Optional[str] = kwargs.pop("unrealized_pnl", None)
        self.aggregated_pnl: Optional[str] = kwargs.pop("aggregated_pnl", None)
        super().__init__(**kwargs)


class UserExpFuturesPositions(BaseResponse):
    def __init__(self, **kwargs):
        self.product_id: Optional[str] = kwargs.pop("product_id", None)
        self.side: Optional[str] = kwargs.pop("side", None)
        self.number_of_contracts: Optional[str] = kwargs.pop(
            "number_of_contracts", None
        )
        self.realized_pnl: Optional[str] = kwargs.pop("realized_pnl", None)
        self.unrealized_pnl: Optional[str] = kwargs.pop("unrealized_pnl", None)
        self.entry_price: Optional[str] = kwargs.pop("entry_price", None)
        super().__init__(**kwargs)


class WSFCMBalanceSummary(BaseResponse):
    def __init__(self, **kwargs):
        self.futures_buying_power: Optional[str] = kwargs.pop(
            "futures_buying_power", None
        )
        self.total_usd_balance: Optional[str] = kwargs.pop("total_usd_balance", None)
        self.cbi_usd_balance: Optional[str] = kwargs.pop("cbi_usd_balance", None)
        self.cfm_usd_balance: Optional[str] = kwargs.pop("cfm_usd_balance", None)
        self.total_open_orders_hold_amount: Optional[str] = kwargs.pop(
            "total_open_orders_hold_amount", None
        )
        self.unrealized_pnl: Optional[str] = kwargs.pop("unrealized_pnl", None)
        self.daily_realized_pnl: Optional[str] = kwargs.pop("daily_realized_pnl", None)
        self.initial_margin: Optional[str] = kwargs.pop("initial_margin", None)
        self.available_margin: Optional[str] = kwargs.pop("available_margin", None)
        self.liquidation_threshold: Optional[str] = kwargs.pop(
            "liquidation_threshold", None
        )
        self.liquidation_buffer_amount: Optional[str] = kwargs.pop(
            "liquidation_buffer_amount", None
        )
        self.liquidation_buffer_percentage: Optional[str] = kwargs.pop(
            "liquidation_buffer_percentage", None
        )
        self.intraday_margin_window_measure: Optional[FCMMarginWindowMeasure] = (
            FCMMarginWindowMeasure(**kwargs.pop("intraday_margin_window_measure"))
            if kwargs.get("intraday_margin_window_measure")
            else None
        )
        self.overnight_margin_window_measure: Optional[FCMMarginWindowMeasure] = (
            FCMMarginWindowMeasure(**kwargs.pop("overnight_margin_window_measure"))
            if kwargs.get("overnight_margin_window_measure")
            else None
        )
        super().__init__(**kwargs)


class FCMMarginWindowMeasure(BaseResponse):
    def __init__(self, **kwargs):
        self.margin_window_type: Optional[str] = kwargs.pop("margin_window_type", None)
        self.margin_level: Optional[str] = kwargs.pop("margin_level", None)
        self.initial_margin: Optional[str] = kwargs.pop("initial_margin", None)
        self.maintenance_margin: Optional[str] = kwargs.pop("maintenance_margin", None)
        self.liquidation_buffer_percentage: Optional[str] = kwargs.pop(
            "liquidation_buffer_percentage", None
        )
        self.total_hold: Optional[str] = kwargs.pop("total_hold", None)
        self.futures_buying_power: Optional[str] = kwargs.pop(
            "futures_buying_power", None
        )
        super().__init__(**kwargs)
