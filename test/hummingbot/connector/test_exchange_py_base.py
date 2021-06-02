import unittest
from decimal import Decimal
from hummingbot.connector.exchange_py_base import ExchangePyBase


class ExchangeBasePyBaseUnitTest(unittest.TestCase):

    def test_quantize_value(self):
        value: Decimal = Decimal("1.16")
        step: Decimal = Decimal("1")
        self.assertEqual(ExchangePyBase.quantize_value(value, step), Decimal("1"))
        step: Decimal = Decimal("0.05")
        self.assertEqual(ExchangePyBase.quantize_value(value, step), Decimal("1.15"))
        step: Decimal = Decimal("0.1")
        self.assertEqual(ExchangePyBase.quantize_value(value, step), Decimal("1.2"))
