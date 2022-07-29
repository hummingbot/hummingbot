from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BtseOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        """
        >>>> Transform Follow Data:
            {
                "buyQuote": [
                    {
                    "price": "36371.0",
                    "size": "0.01485"
                    }
                ],
                "sellQuote": [
                    {
                    "price": "36380.5",
                    "size": "0.01782"
                    }
                ],
                "timestamp": 1624989459489,
                "symbol": "BTC-USD"
            }
        >>>> To Follow:
        {
            "bids": [
                [
                "4.00000000",     // PRICE
                "431.00000000"    // QTY
                ]
            ],
            "asks": [
                [
                "4.00000200",
                "12.00000000"
                ]
            ]
        }
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["timestamp"],
            "bids": [[elem["price"], elem["size"]] for elem in msg["sellQuote"]],
            "asks": [[elem["price"], elem["size"]] for elem in msg["buyQuote"]]
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
        """
        Message:
        {
            "bids": [],
            "asks": [
            [
                "59367.5",
                "2.15622"
            ],
            [
                "59325.5",
                "0"
            ]
            ],
            "seqNum": 628283,
            "prevSeqNum": 628282,
            "type": "delta", // 'snapshot'
            "timestamp": 1565135165600,
            "symbol": "BTC-USD"
        }
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "first_update_id": msg["prevSeqNum"],
            "update_id": msg["seqNum"],
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
        """
        Message Dict[str, any]:
        {
            "symbol": "BTC-USD",
            "side": "SELL",
            "size": 0.007,
            "price": 5302.8,
            "tradeId": 118974855,
            "timestamp": 1584446020295
        }
        """
        if metadata:
            msg.update(metadata)
        ts = msg["timestamp"]
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["side"] == "SELL" else float(TradeType.BUY.value),
            "trade_id": msg["tradeId"],
            "update_id": ts,
            "price": f'{msg["price"]}',
            "amount": f'{msg["size"]}'
        }, timestamp=ts * 1e-3)
