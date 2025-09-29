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
                "update_id": int(timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp
        )
    
    @classmethod
    def diff_message_from_exchange(
            cls, msg: Dict, timestamp: float,
            metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        
        bids = [[Decimal(str(bid["price"])), Decimal(str(bid["amount"]))] 
                for bid in msg.get("bids", [])]
        asks = [[Decimal(str(ask["price"])), Decimal(str(ask["amount"]))] 
                for ask in msg.get("asks", [])]
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": msg.get("trading_pair"),
                "update_id": int(timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp
        )
    
    @classmethod
    def trade_message_from_exchange(
            cls, msg: Dict, timestamp: float,
            metadata: Optional[Dict] = None) -> OrderBookMessage:
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
