from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual.grvt_enums import GrvtChannel, GrvtOrderType


class GrvtEnumsTests(TestCase):
    def test_order_type_enum(self):
        self.assertEqual("limit", GrvtOrderType.LIMIT.value)

    def test_channel_enum(self):
        self.assertEqual("trades", GrvtChannel.TRADES.value)
