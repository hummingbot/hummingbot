from typing import Dict, Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class CubeOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None,
                                       price_scaler: float = 1,
                                       quantity_scaler: float = 1) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :param price_scaler: the price scaler to apply to the price levels
        :param quantity_scaler: the quantity scaler to apply to the quantity levels
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)

        levels = msg["result"]["levels"]

        # bids = [OrderBookRow(float(level["price"]), float(level["quantity"]), msg["result"]["lastTransactTime"]) for
        #         level in levels if level["side"] == 0]
        # asks = [OrderBookRow(float(level["price"]), float(level["quantity"]), msg["result"]["lastTransactTime"]) for
        #         level in levels if level["side"] == 1]

        bids = [OrderBookRow(float(level["price"]) * price_scaler, float(level["quantity"]) * quantity_scaler,
                             msg["result"]["lastTransactTime"]) for
                level in levels if level["side"] == 0]
        asks = [OrderBookRow(float(level["price"]) * price_scaler, float(level["quantity"]) * quantity_scaler,
                             msg["result"]["lastTransactTime"]) for
                level in levels if level["side"] == 1]

        content = {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
        }

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=timestamp)

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
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "first_update_id": msg["update_id"],
            "update_id": msg["update_id"],
            "bids": msg["bids"],
            "asks": msg["asks"]
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
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            # "trade_type": float(TradeType.SELL.value) if msg["m"] else float(TradeType.BUY.value),
            "trade_type": msg["trade_type"],
            "trade_id": msg["trade_id"],
            "update_id": msg["transact_time"],
            "price": msg["price"],
            "amount": msg["fill_quantity"]
        }, timestamp=msg["timestamp"])
