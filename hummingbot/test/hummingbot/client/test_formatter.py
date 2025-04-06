import unittest
from decimal import Decimal

from hummingbot.client import format_decimal, FLOAT_PRINTOUT_PRECISION


class FormatterTest(unittest.TestCase):
    def test_precision_assumption(self):
        self.assertEqual(8, FLOAT_PRINTOUT_PRECISION)  # test cases must be adapted on precision change

    def test_format_float_decimal_places_rounded(self):
        n = 0.987654321
        s = format_decimal(n)
        self.assertEqual("0.98765432", s)

    def test_format_float_places_no_rounding(self):
        n = 0.21
        s = format_decimal(n)
        self.assertEqual("0.21", s)

    def test_format_large_float(self):
        n = 987654321.0
        s = format_decimal(n)
        self.assertEqual("987654321", s)

    def test_format_decimal_obj_decimal_places_rounded(self):
        n = Decimal("0.987654321")
        s = format_decimal(n)
        self.assertEqual("0.98765432", s)

    def test_format_decimal_obj_places_no_rounding(self):
        n = Decimal("0.21")
        s = format_decimal(n)
        self.assertEqual("0.21", s)

    def test_format_large_decimal_obj(self):
        n = Decimal("987654321.0")
        s = format_decimal(n)
        self.assertEqual("987654321", s)
