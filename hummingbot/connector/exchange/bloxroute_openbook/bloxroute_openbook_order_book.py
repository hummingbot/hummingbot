from dataclasses import dataclass
from typing import Dict, List, Optional

from bxsolana_trader_proto import GetOrderbookResponse, api
from bxsolana_trader_proto.api import OrderbookItem

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_utils import truncate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow


@dataclass
class Orderbook:
    asks: List[api.OrderbookItem]
    bids: List[api.OrderbookItem]


@dataclass
class OrderbookInfo:
    best_ask_price: float
    best_ask_size: float
    best_bid_price: float
    best_bid_size: float
    latest_order_book: Orderbook
    timestamp: float


@dataclass
class OrderStatusInfo:
    order_status: api.OrderStatus
    quantity_released: float
    quantity_remaining: float
    side: api.Side
    fill_price: float
    order_price: float
    client_order_i_d: int
    timestamp: float


class BloxrouteOpenbookOrderBook(OrderBook):
    def apply_orderbook_snapshot(
        self, msg: Orderbook, timestamp: float
    ):
        asks = orders_to_orderbook_rows(msg.asks)
        bids = orders_to_orderbook_rows(msg.bids)
        timestamp_int = normalized_timestamp(timestamp)

        self.apply_snapshot(
            asks=asks,
            bids=bids,
            update_id=timestamp_int,
        )


def orders_to_orderbook_rows(orders: List[OrderbookItem]) -> List[OrderBookRow]:
    orderbook_rows = []
    for order in orders:
        orderbook_rows.append(order_to_orderbook_row(order))

    return orderbook_rows


def order_to_orderbook_row(order: OrderbookItem) -> OrderBookRow:
    return OrderBookRow(price=order.price, amount=order.size, update_id=truncate(order.client_order_i_d, 7))


def normalized_timestamp(num: float) -> int:
    integer = int(num)
    if len(str(integer)) <= 7:
        return integer
    else:
        return truncate(integer, 7)

