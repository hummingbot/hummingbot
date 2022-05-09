import unittest

from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_order_status import BitmexPerpetualOrderStatus


class BitmexPerpetualOrderStatusUnitTests(unittest.TestCase):
    def test_ge(self):
        status_1 = BitmexPerpetualOrderStatus.New
        status_2 = BitmexPerpetualOrderStatus.PartiallyFilled

        self.assertTrue(status_2 >= status_1)
        self.assertEqual(status_2.__ge__(1), NotImplemented)

    def test_gt(self):
        status_1 = BitmexPerpetualOrderStatus.Canceled
        status_2 = BitmexPerpetualOrderStatus.FAILURE

        self.assertTrue(status_2 > status_1)
        self.assertEqual(status_2.__gt__(1), NotImplemented)

    def test_le(self):
        status_1 = BitmexPerpetualOrderStatus.New
        status_2 = BitmexPerpetualOrderStatus.Canceled

        self.assertTrue(status_1 <= status_2)
        self.assertEqual(status_2.__le__(1), NotImplemented)

    def test_lt(self):
        status_1 = BitmexPerpetualOrderStatus.PartiallyFilled
        status_2 = BitmexPerpetualOrderStatus.FAILURE

        self.assertTrue(status_1 < status_2)
        self.assertEqual(status_2.__lt__(1), NotImplemented)
