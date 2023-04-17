from enum import Enum
from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

from hummingbot.connector.exchange.foxbit import (
    foxbit_constants as CONSTANTS,
)

class FoxbitTradeFields(Enum):
    ID = 0
    INSTRUMENTID = 1
    VOLUME = 2
    PRICE = 3
    ORDERMAKERID = 4
    ORDERTAKERID = 5
    CREATEDAT = 6
    TREND = 7
    SIDE = 8
    FIXED_BOOL = 9
    FIXED_INT = 10


class FoxbitOrderBookFields(Enum):
    MDUPDATEID = 0
    ACCOUNTS = 1
    ACTIONDATETIME = 2
    ACTIONTYPE = 3
    LASTTRADEPRICE = 4
    ORDERS = 5
    PRICE = 6
    PRODUCTPAIRCODE = 7
    QUANTITY = 8
    SIDE = 9

class FoxbitOrderBookAction(Enum):
    NEW = 0
    UPDATE = 1
    DELETION = 2

class FoxbitOrderBookSide(Enum):
    BID = 0
    ASK = 1

class FoxbitOrderBook(OrderBook):

    _trading_pair = ''
    _bids = {}
    _asks = {}

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None,
                                       ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)

        if msg["trading_pair"] != cls._trading_pair:
            cls._trading_pair = msg["trading_pair"]
            cls._bids = {}
            cls._asks = {}

        for item in msg["bids"]:
            cls.update_order_book('%.10f' % float(item[1]), 
                                  '%.10f' % float(item[0]), 
                                  FoxbitOrderBookSide.BID, 
                                  FoxbitOrderBookAction.NEW)

        for item in msg["asks"]:
            cls.update_order_book('%.10f' % float(item[1]), 
                                  '%.10f' % float(item[0]), 
                                  FoxbitOrderBookSide.ASK, 
                                  FoxbitOrderBookAction.NEW)

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "first_update_id": msg["sequence_id"],
            "update_id": msg["sequence_id"],
            "bids": [[price, quantity] for price, quantity in cls._bids.items()],
            "asks": [[price, quantity] for price, quantity in cls._asks.items()]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None,
                                   ) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """

        if msg[FoxbitOrderBookFields.SIDE.value] == 0:
            cls.update_order_book('%.10f' % float(msg[FoxbitOrderBookFields.QUANTITY.value]), 
                                  '%.10f' % msg[FoxbitOrderBookFields.PRICE.value],
                                   FoxbitOrderBookSide.BID, 
                                   msg[FoxbitOrderBookFields.ACTIONTYPE.value])
        elif msg[FoxbitOrderBookFields.SIDE.value] == 1:
            cls.update_order_book('%.10f' % float(msg[FoxbitOrderBookFields.QUANTITY.value]), 
                                  '%.10f' % msg[FoxbitOrderBookFields.PRICE.value], 
                                  FoxbitOrderBookSide.ASK, 
                                  msg[FoxbitOrderBookFields.ACTIONTYPE.value])

        return OrderBookMessage(
            OrderBookMessageType.DIFF, {
                "trading_pair": metadata["trading_pair"],
                "first_update_id": int(metadata["first_update_id"]),
                "update_id": int(msg[FoxbitOrderBookFields.MDUPDATEID.value]),
                "bids":  [[price, quantity] for price, quantity in cls._bids.items()],
                "asks":  [[price, quantity] for price, quantity in cls._asks.items()],
            }, timestamp=int(msg[FoxbitOrderBookFields.ACTIONDATETIME.value])
        )

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, any],
                                    metadata: Optional[Dict] = None,
                                    ):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        ts = int(msg[FoxbitTradeFields.CREATEDAT.value])
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": metadata["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg[FoxbitTradeFields.SIDE.value] == 1 else float(TradeType.BUY.value),
            "trade_id": msg[FoxbitTradeFields.ID.value],
            "update_id": ts,
            "price": '%.10f' % float(msg[FoxbitTradeFields.PRICE.value]),
            "amount": msg[FoxbitTradeFields.VOLUME.value]
        }, timestamp=ts * 1e-3)

    @classmethod
    def update_order_book(cls, quantity: str, price: str, side: FoxbitOrderBookSide, action: FoxbitOrderBookAction):
        q = float(quantity)
        p = float(price)

        if side == FoxbitOrderBookSide.BID:
            if action == FoxbitOrderBookAction.DELETION:
                del cls._bids[p]
            else:
                cls._bids[p] = q

            if len(cls._bids) > CONSTANTS.ORDER_BOOK_DEPTH:
                min_bid = min(cls._bids.keys())
                del cls._bids[min_bid]
            
            cls._bids = dict(sorted(cls._bids.items(), reverse=True))
        
        else:
            if action == FoxbitOrderBookAction.DELETION:
                del cls._asks[p]
            else:
                cls._asks[p] = q
            
            if len(cls._asks) > CONSTANTS.ORDER_BOOK_DEPTH:
                max_ask = max(cls._asks.keys())
                del cls._asks[max_ask]
            
            cls._asks = dict(sorted(cls._asks.items()))
 