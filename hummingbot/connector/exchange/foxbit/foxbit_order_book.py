from enum import Enum
from typing import Dict, Optional

from hummingbot.connector.exchange.foxbit import foxbit_constants as CONSTANTS
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class FoxbitTradeFields(Enum):
    ID = 0
    INSTRUMENTID = 1
    QUANTITY = 2
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


class FoxbitOrderBookItem(Enum):
    PRICE = 0
    QUANTITY = 1


class FoxbitOrderBook(OrderBook):
    _bids = {}
    _asks = {}

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
            "amount": '%.10f' % float(msg[FoxbitTradeFields.QUANTITY.value])
        }, timestamp=ts * 1e-3)

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

        sample of msg {'sequence_id': 5972127, 'asks': [['140999.9798', '0.00007093'], ['140999.9899', '0.10646516'], ['140999.99', '0.01166287'], ['141000.0', '0.00024751'], ['141049.9999', '0.3688'], ['141050.0', '0.00184094'], ['141099.0', '0.00007087'], ['141252.9994', '0.02374105'], ['141253.0', '0.5786'], ['141275.0', '0.00707839'], ['141299.0', '0.00007077'], ['141317.9492', '0.814357'], ['141323.9741', '0.0039086'], ['141339.358', '0.64833964']], 'bids': [[['140791.4571', '0.0000569'], ['140791.4471', '0.00000028'], ['140791.4371', '0.0000289'], ['140791.4271', '0.00018672'], ['140512.4635', '0.06396371'], ['140512.4632', '0.3688'], ['140506.0', '0.5786'], ['140499.5014', '0.1'], ['140377.2678', '0.00976774'], ['140300.0', '0.005866'], ['140054.3859', '0.14746'], ['140054.1159', '3.45282018'], ['140032.8321', '1.2267452'], ['140025.553', '1.12483605']]}
        """
        cls.logger().info(f'Refreshing order book to {metadata["trading_pair"]}.')

        cls._bids = {}
        cls._asks = {}

        for item in msg["bids"]:
            cls.update_order_book('%.10f' % float(item[FoxbitOrderBookItem.QUANTITY.value]),
                                  '%.10f' % float(item[FoxbitOrderBookItem.PRICE.value]),
                                  FoxbitOrderBookSide.BID)

        for item in msg["asks"]:
            cls.update_order_book('%.10f' % float(item[FoxbitOrderBookItem.QUANTITY.value]),
                                  '%.10f' % float(item[FoxbitOrderBookItem.PRICE.value]),
                                  FoxbitOrderBookSide.ASK)

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": metadata["trading_pair"],
            "update_id": int(msg["sequence_id"]),
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

        sample of msg = [5971940, 0, 1683735920192, 2, 140999.9798, 0, 140688.6227, 1, 0, 0]
        """
        trading_pair = metadata["trading_pair"]
        order_book_id = int(msg[FoxbitOrderBookFields.MDUPDATEID.value])
        prc = '%.10f' % float(msg[FoxbitOrderBookFields.PRICE.value])
        qty = '%.10f' % float(msg[FoxbitOrderBookFields.QUANTITY.value])

        if msg[FoxbitOrderBookFields.ACTIONTYPE.value] == FoxbitOrderBookAction.DELETION.value:
            qty = '0'

        if msg[FoxbitOrderBookFields.SIDE.value] == FoxbitOrderBookSide.BID.value:

            return OrderBookMessage(
                OrderBookMessageType.DIFF, {
                    "trading_pair": trading_pair,
                    "update_id": order_book_id,
                    "bids": [[prc, qty]],
                    "asks": [],
                }, timestamp=int(msg[FoxbitOrderBookFields.ACTIONDATETIME.value]))

        if msg[FoxbitOrderBookFields.SIDE.value] == FoxbitOrderBookSide.ASK.value:
            return OrderBookMessage(
                OrderBookMessageType.DIFF, {
                    "trading_pair": trading_pair,
                    "update_id": order_book_id,
                    "bids": [],
                    "asks": [[prc, qty]],
                }, timestamp=int(msg[FoxbitOrderBookFields.ACTIONDATETIME.value]))

    @classmethod
    def update_order_book(cls, quantity: str, price: str, side: FoxbitOrderBookSide):
        q = float(quantity)
        p = float(price)

        if side == FoxbitOrderBookSide.BID:
            cls._bids[p] = q
            if len(cls._bids) > CONSTANTS.ORDER_BOOK_DEPTH:
                min_bid = min(cls._bids.keys())
                del cls._bids[min_bid]

            cls._bids = dict(sorted(cls._bids.items(), reverse=True))
            return

        if side == FoxbitOrderBookSide.ASK:
            cls._asks[p] = q
            if len(cls._asks) > CONSTANTS.ORDER_BOOK_DEPTH:
                max_ask = max(cls._asks.keys())
                del cls._asks[max_ask]

            cls._asks = dict(sorted(cls._asks.items()))
            return
