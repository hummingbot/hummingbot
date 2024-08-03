from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class HashkeyOrderBook(OrderBook):
    @classmethod
<<<<<<< HEAD:hummingbot/connector/exchange/hashkey/hashkey_order_book.py
    def snapshot_message_from_exchange_websocket(cls,
                                                 msg: Dict[str, any],
                                                 timestamp: float,
                                                 metadata: Optional[Dict] = None) -> OrderBookMessage:
=======
    def snapshot_message_from_exchange(
        cls, msg: Dict[str, any], timestamp: float, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors):hummingbot/connector/exchange/chainflip_lp/chainflip_lp_order_book.py
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
<<<<<<< HEAD:hummingbot/connector/exchange/hashkey/hashkey_order_book.py
        ts = msg["t"]
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": ts,
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=timestamp)

    @classmethod
    def snapshot_message_from_exchange_rest(cls,
                                            msg: Dict[str, any],
                                            timestamp: float,
                                            metadata: Optional[Dict] = None) -> OrderBookMessage:
=======
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": msg["lastUpdateId"],
                "bids": msg["bids"],
                "asks": msg["asks"],
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls, msg: Dict[str, any], timestamp: Optional[float] = None, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors):hummingbot/connector/exchange/chainflip_lp/chainflip_lp_order_book.py
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
<<<<<<< HEAD:hummingbot/connector/exchange/hashkey/hashkey_order_book.py
        ts = msg["t"]
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": ts,
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=timestamp)
=======
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": msg["trading_pair"],
                "first_update_id": msg["U"],
                "update_id": msg["u"],
                "bids": msg["b"],
                "asks": msg["a"],
            },
            timestamp=timestamp,
        )
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors):hummingbot/connector/exchange/chainflip_lp/chainflip_lp_order_book.py

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
<<<<<<< HEAD:hummingbot/connector/exchange/hashkey/hashkey_order_book.py
        ts = msg["t"]
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.BUY.value) if msg["m"] else float(TradeType.SELL.value),
            "trade_id": ts,
            "update_id": ts,
            "price": msg["p"],
            "amount": msg["q"]
        }, timestamp=ts * 1e-3)
=======
        ts = msg["E"]
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.SELL.value) if msg["m"] else float(TradeType.BUY.value),
                "trade_id": msg["t"],
                "update_id": ts,
                "price": msg["p"],
                "amount": msg["q"],
            },
            timestamp=ts * 1e-3,
        )
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors):hummingbot/connector/exchange/chainflip_lp/chainflip_lp_order_book.py
