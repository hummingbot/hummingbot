"""
Coinmate Exchange Order Book Implementation

This module handles order book data parsing from Coinmate's REST API and
WebSocket feeds.

API Documentation: https://coinmate.docs.apiary.io/
"""
from typing import Dict, Optional
from decimal import Decimal

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)


class CoinmateOrderBook(OrderBook):
    
    @classmethod
    def snapshot_message_from_exchange(
            cls, msg: Dict, timestamp: float,
            metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Convert Coinmate order book snapshot to Hummingbot format.
        https://coinmate.docs.apiary.io/#reference/order-book/get-order-book
        
        {
            "bids": [
                {"price": "49000.0", "amount": "0.5"},
                {"price": "48900.0", "amount": "1.0"}
            ],
            "asks": [
                {"price": "51000.0", "amount": "0.3"}
            ]
        }
        """
        if metadata:
            msg.update(metadata)
        
        bids = [[Decimal(str(bid["price"])), Decimal(str(bid["amount"]))] 
                for bid in msg.get("bids", [])]
        asks = [[Decimal(str(ask["price"])), Decimal(str(ask["amount"]))] 
                for ask in msg.get("asks", [])]
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": msg.get("trading_pair"),
                "update_id": -1,
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp
        )
    
    @classmethod
    def trade_message_from_exchange(
            cls, msg: Dict, timestamp: float,
            metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Convert Coinmate trade message to Hummingbot format.
        https://coinmate.docs.apiary.io/#reference/websocket/new-trades
        
        {
            "date": 1234567890000,
            "price": "50000.0",
            "amount": "0.1",
            "type": "BUY",
            "buyOrderId": "12345",
            "sellOrderId": "67890",
            "transactionId": "987654"
        }
        """
        if metadata:
            msg.update(metadata)
        
        trade_type = TradeType.BUY if msg.get("type") == "BUY" else TradeType.SELL
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": msg.get("trading_pair"),
                "trade_type": trade_type.value,
                "trade_id": msg.get("transactionId", str(int(timestamp * 1000))),
                "update_id": int(timestamp * 1000),
                "price": Decimal(str(msg.get("price", 0))),
                "amount": Decimal(str(msg.get("amount", 0))),
            },
            timestamp=timestamp
        )
