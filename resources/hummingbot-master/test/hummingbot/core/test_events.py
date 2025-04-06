from decimal import Decimal
from unittest import TestCase

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType


class OrderFilledEventTests(TestCase):

    def test_fill_events_created_from_order_book_rows_have_unique_trade_ids(self):
        rows = [OrderBookRow(Decimal(1000), Decimal(1), 1), OrderBookRow(Decimal(1001), Decimal(2), 2)]
        fill_events = OrderFilledEvent.order_filled_events_from_order_book_rows(
            timestamp=1640001112.223,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            trade_fee=AddedToCostTradeFee(),
            order_book_rows=rows
        )

        self.assertEqual("OID1_0", fill_events[0].exchange_trade_id)
        self.assertEqual("OID1_1", fill_events[1].exchange_trade_id)
