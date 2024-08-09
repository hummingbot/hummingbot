# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation, no-member, no-name-in-module
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from binance_order_book v1.0.0 fork
~
"""
# STANDARD MODULES
from typing import Dict, Optional

# HUMMINGBOT MODULES
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.events import TradeType


class GrapheneOrderBook(OrderBook):
    """
    standardizes formatting for trade history and orderbook snapshots
    """

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: raw response from the exchange when requesting the order book
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a formatted OrderBookMessage SNAPSHOT
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": msg["blocktime"],
                "bids": msg["bids"],
                "asks": msg["asks"],
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        GrapheneOrderBook deals only in snapshot messages
        """
        raise NotImplementedError(__doc__)

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, any],
        metadata: Optional[Dict] = None,
    ):
        """
        Creates a trade message with the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a formatted OrderBookMessage TRADE
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.SELL.value)
                if msg["trade_type"] == "SELL"
                else float(TradeType.BUY.value),
                "trade_id": msg["trade_id"],
                "update_id": msg["update_id"],
                "price": msg["price"],
                "amount": msg["amount"],
            },
            timestamp=msg["update_id"] * 1e-3,
        )
