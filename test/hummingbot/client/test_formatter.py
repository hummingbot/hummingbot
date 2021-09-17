import unittest
from decimal import Decimal

from hummingbot.client import format_decimal, FLOAT_PRINTOUT_PRECISION


class FormatterTest(unittest.TestCase):
    def test_precision_assumption(self):
        self.assertEqual(7, FLOAT_PRINTOUT_PRECISION)  # if failed, remaining test case must be adapted

    def test_format_float_decimal_places_rounded(self):
        n = 0.12345678
        s = format_decimal(n)
        self.assertEqual("0.1234568", s)

    def test_format_float_places_no_rounding(self):
        n = 0.12
        s = format_decimal(n)
        self.assertEqual("0.12", s)

    def test_format_large_float(self):
        n = 12345678.0
        s = format_decimal(n)
        self.assertEqual("12345678", s)

    def test_format_decimal_obj_decimal_places_rounded(self):
        n = Decimal("0.12345678")
        s = format_decimal(n)
        self.assertEqual("0.1234568", s)

    def test_format_decimal_obj_places_no_rounding(self):
        n = Decimal("0.12")
        s = format_decimal(n)
        self.assertEqual("0.12", s)

    def test_format_large_decimal_obj(self):
        n = Decimal("12345678.0")
        s = format_decimal(n)
        self.assertEqual("12345678", s)
