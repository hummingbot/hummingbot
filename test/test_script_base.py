#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import unittest
from decimal import Decimal
from statistics import mean
from hummingbot.script.script_base import ScriptBase


class ScriptIteratorUnitTest(unittest.TestCase):

    def test_avg_mid_price(self):
        script_base = ScriptBase()
        script_base.mid_prices = [Decimal("10.1"), Decimal("10.2"), Decimal("10.1"), Decimal("10.2"), Decimal("10.4"),
                                  Decimal("10.5"), Decimal("10.3"), Decimal("10.6"), Decimal("10.7"), Decimal("10.8"),
                                  Decimal("10.0"), Decimal("10.1"), Decimal("10.1"), Decimal("10.1"), Decimal("10.1")]
        avg_price = script_base.avg_mid_price(3, 10)
        # since there is not enough sample size, it should return None
        self.assertTrue(avg_price is None)
        # At interval of 3 and length of 5, these belows are counted as the samples
        samples = [Decimal("10.1"), Decimal("10.5"), Decimal("10.7"), Decimal("10.1"), Decimal("10.1")]
        self.assertEqual(mean(samples), script_base.avg_mid_price(3, 5))
        # At length of 2, only the last two should be used for the avg
        samples = [Decimal("10.1"), Decimal("10.1")]
        self.assertEqual(mean(samples), script_base.avg_mid_price(3, 2))
        # At 100 interval and length of 1, only the last item is counted.
        avg_price = script_base.avg_mid_price(100, 1)
        self.assertEqual(Decimal("10.1"), avg_price)
