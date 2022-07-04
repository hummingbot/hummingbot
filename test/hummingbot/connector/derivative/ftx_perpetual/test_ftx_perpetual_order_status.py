import unittest

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_order_status import FtxPerpetualOrderStatus


class FtxPerpetualOrderStatusUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()

    def test_ge(self):
        status_1 = FtxPerpetualOrderStatus.new
        status_2 = FtxPerpetualOrderStatus.open

        self.assertTrue(status_2 >= status_1)
        self.assertEqual(status_2.__ge__(1), NotImplemented)

    def test_gt(self):
        status_1 = FtxPerpetualOrderStatus.closed
        status_2 = FtxPerpetualOrderStatus.FAILURE

        self.assertTrue(status_2 > status_1)
        self.assertEqual(status_2.__gt__(1), NotImplemented)

    def test_le(self):
        status_1 = FtxPerpetualOrderStatus.new
        status_2 = FtxPerpetualOrderStatus.closed

        self.assertTrue(status_1 <= status_2)
        self.assertEqual(status_2.__le__(1), NotImplemented)

    def test_lt(self):
        status_1 = FtxPerpetualOrderStatus.open
        status_2 = FtxPerpetualOrderStatus.FAILURE

        self.assertTrue(status_1 < status_2)
        self.assertEqual(status_2.__lt__(1), NotImplemented)
