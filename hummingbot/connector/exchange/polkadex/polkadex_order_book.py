from typing import Dict, Optional, List
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)


class PolkadexOrderbook(OrderBook):
    @classmethod
    def snapshot_message_from_exchange(cls, msgs: List[Dict[str, any]], timestamp: float, metadata) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msgs: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """

        bids = []
        asks = []
        for price_level in msgs:
            print("price_level", price_level)
            if price_level["side"] == "BID":
                bids.append((float(price_level["price"]), float(price_level["qty"])))
            else:
                asks.append((float(price_level["price"]), float(price_level["qty"])))


        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": metadata["trading_pair"],
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        if metadata:
            msg.update(metadata)

        bids = []
        asks = []
        for put in msg["puts"]:
            if put["side"] == "BID":
                bids.append((float(put["price"]), float(put["qty"]), float(msg["seq"])))
            else:
                asks.append((float(put["price"]), float(put["qty"]), float(msg["seq"])))
        for dels in msg["dels"]:
            if dels["side"] == "BID":
                bids.append((float(dels["price"]), float(0),float(msg["seq"])))
            else:
                asks.append((float(dels["price"]), float(0),float(msg["seq"])))

        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id":msg["seq"],
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp)

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
        ts = msg["time"]

        if msg["s"] == "BID":
            trade_type = float(TradeType.BUY.value)
        else:
            trade_type = float(TradeType.SELL.value)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": trade_type,
            "trade_id": msg["t"],
            "update_id": ts,
            "price": msg["p"],
            "amount": msg["q"]
        }, timestamp=ts * 1e-3)
