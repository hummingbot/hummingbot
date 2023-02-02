from typing import Dict, List, Optional

from bxsolana_trader_proto import GetOrderbookResponse
from bxsolana_trader_proto.api import OrderbookItem

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class BloxrouteOpenbookOrderBook(OrderBook):
    @classmethod
    def snapshot_message_from_exchange(
        cls, msg: Dict[str, any], timestamp: float, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """

        if msg["orderbook"]:
            if metadata:
                msg.update(metadata)
            orderbook: GetOrderbookResponse = msg["orderbook"]
            return OrderBookMessage(
                OrderBookMessageType.SNAPSHOT,
                {
                    "trading_pair": msg["trading_pair"],
                    "trade_id": timestamp,
                    "update_id": timestamp,
                    "bids": orders_to_orderbook_rows(orderbook.bids),
                    "asks": orders_to_orderbook_rows(orderbook.asks),
                },
                timestamp=timestamp,
            )
        else:
            raise Exception(f"orderbook snapshot update did not contain `orderbook` field: {msg}")


def orders_to_orderbook_rows(orders: List[OrderbookItem]) -> List[OrderBookRow]:
    orderbook_rows = []
    for order in orders:
        orderbook_rows.append(order_to_orderbook_row(order))

    return orderbook_rows


def order_to_orderbook_row(order: OrderbookItem) -> OrderBookRow:
    return OrderBookRow(price=order.price, amount=order.size, update_id=order.order_i_d)
