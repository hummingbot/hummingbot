import unittest

from hummingbot.connector.exchange.bitmex.bitmex_order_status import BitmexOrderStatus


class BitmexOrderStatusUnitTests(unittest.TestCase):
    def test_ge(self):
        status_1 = BitmexOrderStatus.New
        status_2 = BitmexOrderStatus.PartiallyFilled

        self.assertTrue(status_2 >= status_1)
        self.assertEqual(status_2.__ge__(1), NotImplemented)

    def test_gt(self):
        status_1 = BitmexOrderStatus.Canceled
        status_2 = BitmexOrderStatus.FAILURE

        self.assertTrue(status_2 > status_1)
        self.assertEqual(status_2.__gt__(1), NotImplemented)

    def test_le(self):
        status_1 = BitmexOrderStatus.New
        status_2 = BitmexOrderStatus.Canceled

        self.assertTrue(status_1 <= status_2)
        self.assertEqual(status_2.__le__(1), NotImplemented)

    def test_lt(self):
        status_1 = BitmexOrderStatus.PartiallyFilled
        status_2 = BitmexOrderStatus.FAILURE

        self.assertTrue(status_1 < status_2)
        self.assertEqual(status_2.__lt__(1), NotImplemented)
