from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class TegroOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)

        def ensure_price_and_quantity(entry: Dict[str, any]):
            price = entry.get('price', 0.0)
            quantity = entry.get('quantity', 0)
            return [price, quantity]

        trading_pair = msg.get("trading_pair", "")
        time = msg.get("timestamp", "")

        bid_res = msg.get("bids", [])
        ask_res = msg.get("asks", [])
        bids = []
        asks = []

        if len(ask_res) > 0:
            asks = [ensure_price_and_quantity(entry) for entry in msg.get("asks", [])]
        if len(bid_res) > 0:
            bids = [ensure_price_and_quantity(entry) for entry in msg.get("bids", [])]

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": time,
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

        def ensure_price_and_quantity(entry: Dict[str, any]):
            price = entry.get('price', 0.0)
            quantity = entry.get('quantity', 0)
            return [price, quantity]
        # Ensure 'price' and 'quantity' keys exist in each entry, defaulting to 0 if missing
        bid_res = msg["data"].get("bids", [])
        ask_res = msg["data"].get("asks", [])
        bids = []
        asks = []

        if len(ask_res) > 0:
            asks = [ensure_price_and_quantity(entry) for entry in msg["data"].get("asks", [])]
        if len(bid_res) > 0:
            bids = [ensure_price_and_quantity(entry) for entry in msg["data"].get("bids", [])]

        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["data"]["timestamp"],
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None, metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = timestamp
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["data"]["symbol"],
            "trade_type": float(TradeType.BUY.value) if msg["data"]["is_buyer_maker"] else float(TradeType.SELL.value),
            "trade_id": msg["data"]["id"],
            "update_id": ts,
            "price": msg["data"]["price"],
            "amount": msg["data"]["amount"]
        }, timestamp=ts * 1e-3)
