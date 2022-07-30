from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class PolkadexOrderbook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls, msgs: List[Dict[str, any]], timestamp: float, metadata) -> OrderBookMessage:
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
        print("Recvd snapshot msgs: ",msgs)
        for price_level in msgs:
            if price_level["s"] == "Bid":
                bids.append((float(price_level["p"]), float(price_level["q"]), int(-1)))
            else:
                asks.append((float(price_level["price"]), float(price_level["qty"]), int(-1)))

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
        {
          "data": {
            "websocket_streams": {
              "data": "[{\"side\":\"Ask\",\"price\":3,\"qty\":2,\"seq\":0},{\"side\":\"Bid\",\"price\":2,\"qty\":2,\"seq\":0}]"
            }
          }
        }
        """
        changes = msg["data"]["websocket_streams"]["data"]
        if metadata:
            msg.update(metadata)

        bids = []
        asks = []
        for change in changes:
            if change["side"] == "Ask":
                asks.append((float(change["price"]), float(change["qty"]), float(change["seq"])))
            else:
                bids.append((float(change["price"]), float(change["qty"]), float(change["seq"])))

        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id": int(msg["seq"]),
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



        expected data structure
        {
          "data": {
            "websocket_streams": {
              "data": "{\"m\":\"PDEX-1\",\"p\":10,\"q\":1000,\"tid\":0,\"t\":1234567890}"
            }
          }
        }
        """
        msg = msg["data"]["websocket_streams"]["data"]
        if metadata:
            msg.update(metadata)

        ts = msg["t"]

        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["m"],
            "trade_id": msg["tid"],
            "update_id": ts,
            "price": float(msg["p"]),
            "amount": float(msg["q"])
        }, timestamp=ts * 1e-3)
