import logging
from typing import (
    Dict,
    Optional
)

import ujson
from aiokafka import ConsumerRecord

from hummingbot.connector.exchange.blocktane.blocktane_utils import convert_from_exchange_trading_pair
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)
from hummingbot.logger import HummingbotLogger

_bob_logger = None

cdef class BlocktaneOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _bob_logger
        if _bob_logger is None:
            _bob_logger = logging.getLogger(__name__)
        return _bob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,  # not sure whether this is correct
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        def adjust_empty_amounts(levels):
            result = []
            for level in levels:
                if len(level) == 0:
                    continue
                if len(level) < 2 or level[1] == '':
                    result.append([level[0], "0"])
                else:
                    result.append(level)
            return result

        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["pair"],
            "update_id": timestamp,
            "bids": adjust_empty_amounts([msg["bids"]]),
            "asks": adjust_empty_amounts([msg["asks"]])
        }, timestamp=timestamp)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record.value.decode("utf-8"))
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["pair"],
            "update_id": record.timestamp,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=record.timestamp * 1e-3)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record.value.decode("utf-8"))
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["pair"],
            "update_id": record.timestamp,
            "bids": msg["bids"],
            "asks": msg["asks"],

        }, timestamp=record.timestamp * 1e-3)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        # {'fthusd.trades': {'trades': [{'tid': 9, 'taker_type': 'sell', 'date': 1586958619, 'price': '51.0', 'amount': '0.02'}]}}
        if metadata:
            msg.update(metadata)

        # cls.logger().error("Message from exchange: " + str(msg))

        msg = msg.popitem()
        # cls.logger().error(str(msg))

        market = convert_from_exchange_trading_pair(msg[0].split('.')[0])
        trade = msg[1]["trades"][0]
        ts = trade['date']
        # cls.logger().error(str(market) + " " + str(trade) + " " + str(ts))
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": market,
            "trade_type": trade['taker_type'],
            "trade_id": trade["tid"],
            "update_id": ts,
            "price": trade["price"],
            "amount": trade["amount"]
        }, timestamp=ts)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = BlocktaneOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
