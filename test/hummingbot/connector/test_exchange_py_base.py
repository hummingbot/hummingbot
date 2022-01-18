import unittest
from decimal import Decimal
from hummingbot.connector.exchange_py_base import ExchangePyBase


class ExchangeBasePyBaseUnitTest(unittest.TestCase):

    def test_quantize_value(self):
        value: Decimal = Decimal("1.16")
        step: Decimal = Decimal("1")
        self.assertEqual(Decimal("1"), ExchangePyBase.quantize_value(value, step))

        step: Decimal = Decimal("0.05")
        self.assertEqual(Decimal("1.15"), ExchangePyBase.quantize_value(value, step))

        step: Decimal = Decimal("0.1")
        self.assertEqual(Decimal("1.1"), ExchangePyBase.quantize_value(value, step))

        value = Decimal("1.95")
        step = Decimal("1")
        self.assertEqual(Decimal("1"), ExchangePyBase.quantize_value(value, step))

        value = Decimal("0.95")
        step = Decimal("1")
        self.assertEqual(Decimal("0"), ExchangePyBase.quantize_value(value, step))
