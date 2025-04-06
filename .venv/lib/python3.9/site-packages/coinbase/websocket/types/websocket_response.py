from typing import List, Optional

from coinbase.websocket.types.base_response import BaseResponse
from coinbase.websocket.types.misc_types import (
    L2Update,
    UserOrders,
    UserPositions,
    WSCandle,
    WSFCMBalanceSummary,
    WSHistoricalMarketTrade,
    WSProduct,
    WSTicker,
)


class WebsocketResponse(BaseResponse):
    def __init__(self, data):
        self.channel = data.pop("channel")
        self.client_id = data.pop("client_id")
        self.timestamp = data.pop("timestamp")
        self.sequence_num = data.pop("sequence_num")
        self.events = [
            Event(event_data, self.channel) for event_data in data.pop("events")
        ]

        super().__init__(**data)


class Event(BaseResponse):
    def __init__(self, data, channel):
        if channel == "heartbeats":
            self.current_time = data.pop("current_time", None)
            self.heartbeat_counter = data.pop("heartbeat_counter", None)
        elif channel == "candles":
            self.type = data.pop("type", None)
            self.candles: List[WSCandle] = (
                [WSCandle(**ws_candle) for ws_candle in data.pop("candles", [])]
                if "candles" in data
                else None
            )
        elif channel == "market_trades":
            self.type = data.pop("type", None)
            self.trades: List[WSHistoricalMarketTrade] = (
                [
                    WSHistoricalMarketTrade(**ws_trades)
                    for ws_trades in data.pop("trades", [])
                ]
                if "trades" in data
                else None
            )
        elif channel == "status":
            self.type = data.pop("type", None)
            self.products: List[WSProduct] = (
                [WSProduct(**ws_product) for ws_product in data.pop("products", [])]
                if "products" in data
                else None
            )
        elif channel == "ticker" or channel == "ticker_batch":
            self.type = data.pop("type", None)
            self.tickers: List[WSTicker] = (
                [WSTicker(**ws_ticker) for ws_ticker in data.pop("tickers", [])]
                if "tickers" in data
                else None
            )
        elif channel == "l2_data":
            self.type = data.pop("type", None)
            self.product_id = data.pop("product_id", None)
            self.updates: List[L2Update] = (
                [L2Update(**l2_update) for l2_update in data.pop("updates", [])]
                if "updates" in data
                else None
            )
        elif channel == "user":
            self.type = data.pop("type", None)
            self.orders: Optional[List[UserOrders]] = (
                [UserOrders(**user_order) for user_order in data.pop("orders", [])]
                if data.get("orders") is not None
                else None
            )
            self.positions: Optional[UserPositions] = (
                UserPositions(**data.pop("positions")) if "positions" in data else None
            )
        elif channel == "futures_balance_summary":
            self.type = data.pop("type", None)
            self.fcm_balance_summary: WSFCMBalanceSummary = (
                WSFCMBalanceSummary(**data.pop("fcm_balance_summary"))
                if data.get("fcm_balance_summary")
                else None
            )

        super().__init__(**data)
