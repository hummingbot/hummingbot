import time
from typing import Dict, List, Optional

from hummingbot.connector.exchange.polkadex import polkadex_utils as p_utils
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class PolkadexOrderbook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls, msgs: List[Dict[str, any]], timestamp: float, metadata) -> OrderBookMessage:
        # print("Snapshot called")

        """
        Creates a snapshot message with the order book snapshot message
        :param msgs: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange


        Expected msgs
        [
            {
              "p": "3",
              "q": "2",
              "s": "Ask"
            },
            {
              "p": "2",
              "q": "2",
              "s": "Bid"
            }
       ]
        """

        bids = []
        asks = []
        for price_level in msgs:
            if price_level["s"] == "Bid":
                bids.append((p_utils.parse_price_or_qty(price_level["p"]), p_utils.parse_price_or_qty(price_level["q"]), int(-1)))
            else:
                asks.append((p_utils.parse_price_or_qty(price_level["p"]), p_utils.parse_price_or_qty(price_level["q"]), int(-1)))

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": metadata["trading_pair"],
            "bids": bids,
            "asks": asks,
            "update_id": -1
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

        Expected data structure
        {'side': 'Ask', 'price': '11.11', 'qty': '10.1', 'id': 263, 'market': 'PDEX-1'}
        """
        if metadata:
            msg.update(metadata)

        market = msg["market"]

        if msg["qty"] == '0':
            msg["price"] = '0'

        bids = []
        asks = []
        seq = 0
        if msg["side"] == "Ask":
            asks.append((p_utils.parse_price_or_qty(msg["price"]), p_utils.parse_price_or_qty(msg["qty"]), float(msg["id"])))
            seq = float(msg["id"])
        else:
            bids.append((p_utils.parse_price_or_qty(msg["price"]), p_utils.parse_price_or_qty(msg["qty"]), float(msg["id"])))
            seq = float(msg["id"])

        if asks:
            var = OrderBookMessage(OrderBookMessageType.DIFF, {
                "trading_pair": market,
                "update_id": int(seq),
                "asks": asks,
                "bids": []
            }, timestamp=time.time())
        else:
            var = OrderBookMessage(OrderBookMessageType.DIFF, {
                "trading_pair": market,
                "update_id": int(seq),
                "bids": bids,
                "asks": []
            }, timestamp=time.time())
        return var

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

        # TODO can we directly set it
        ts = msg["t"]

        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["m"],
            "trade_id": msg["tid"],
            "update_id": msg["t"],
            "price": p_utils.parse_price_or_qty(msg["p"]),
            "amount": p_utils.parse_price_or_qty(msg["q"]),
            "trade_type": float(2)
        }, timestamp=ts)
