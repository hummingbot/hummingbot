import time
import unittest

from hummingbot.core.data_type.order_book_message import OrderBookMessage, \
    OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class OrderBookMessageTest(unittest.TestCase):
    def test_update_id(self):
        update_id = "someId"

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        self.assertEqual(update_id, msg.update_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        self.assertEqual(update_id, msg.update_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertEqual(-1, msg.update_id)

    def test_first_update_id(self):
        first_update_id = "firstUpdateId"
        update_id = "someId"

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertEqual(-1, msg.first_update_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": update_id,
                "first_update_id": first_update_id,
            },
            timestamp=time.time(),
        )
        self.assertEqual(first_update_id, msg.first_update_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertEqual(-1, msg.first_update_id)

    def test_trade_id(self):
        trade_id = "someTradeId"

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertEqual(-1, msg.trade_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertEqual(-1, msg.trade_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"trade_id": trade_id},
            timestamp=time.time(),
        )
        self.assertEqual(trade_id, msg.trade_id)

    def test_trading_pair(self):
        trading_pair = "BTC-USDT"

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"trading_pair": trading_pair},
            timestamp=time.time(),
        )
        self.assertEqual(trading_pair, msg.trading_pair)

    def test_bids_and_asks(self):
        update_id = "someId"
        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "update_id": update_id,
                "asks": [(1, 2), (3, 4)],
                "bids": [(5, 6), (7, 8)],
            },
            timestamp=time.time(),
        )

        asks = msg.asks
        self.assertEqual(2, len(asks))
        self.assertTrue(isinstance(asks[0], OrderBookRow))
        self.assertEqual(1, asks[0].price)
        self.assertEqual(2, asks[0].amount)
        self.assertEqual(update_id, asks[0].update_id)

        bids = msg.bids
        self.assertEqual(2, len(bids))
        self.assertTrue(isinstance(bids[0], OrderBookRow))
        self.assertEqual(5, bids[0].price)
        self.assertEqual(6, bids[0].amount)
        self.assertEqual(update_id, bids[0].update_id)

    def test_has_update_id(self):
        update_id = "someId"

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        self.assertTrue(msg.has_update_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        self.assertTrue(msg.has_update_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertFalse(msg.has_update_id)

    def test_has_trade_id(self):
        trade_id = "someTradeId"

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertFalse(msg.has_trade_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertFalse(msg.has_trade_id)

        msg = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"trade_id": trade_id},
            timestamp=time.time(),
        )
        self.assertTrue(msg.has_trade_id)

    def test_equality(self):
        trade_id = "someTradeId"
        update_id = "someId"

        snapshot1 = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        snapshot2 = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        diff1 = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        diff2 = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        trade1 = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"trade_id": trade_id},
            timestamp=time.time(),
        )
        trade2 = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"trade_id": trade_id},
            timestamp=time.time(),
        )

        self.assertNotEqual(snapshot1, diff1)
        self.assertNotEqual(snapshot1, trade1)
        self.assertNotEqual(diff1, trade1)
        self.assertEqual(snapshot1, snapshot2)
        self.assertEqual(diff1, diff2)
        self.assertEqual(trade1, trade2)

    def test_larger_than(self):
        t = time.time()
        trade1 = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"trade_id": 5},
            timestamp=t,
        )
        trade2 = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"trade_id": 6},
            timestamp=time.time() + 1,
        )
        snapshot1 = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": 1},
            timestamp=time.time() + 2,
        )
        snapshot2 = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": 3},
            timestamp=time.time() + 3,
        )
        diff1 = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": 2},
            timestamp=time.time() + 4,
        )
        diff2 = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": 2},
            timestamp=t,
        )

        self.assertTrue(trade1 < trade2)  # based on id
        self.assertTrue(snapshot1 < snapshot2)  # based on id
        self.assertTrue(snapshot1 < diff1)  # based on id
        self.assertTrue(diff1 < snapshot2)  # based on id
        self.assertTrue(trade1 < snapshot1)  # based on timestamp
        self.assertTrue(diff2 < trade1)  # if same ts, ob messages < trade messages
