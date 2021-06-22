#!/usr/bin/env python

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

    def test_take_samples(self):
        script_base = ScriptBase()
        a_list = [1, 2, 3, 4, 5, 6, 7]
        samples = script_base.take_samples(a_list, 3, 10)
        # since there is not enough sample size, it should return None
        self.assertTrue(samples is None)
        # At interval of 3 and length of 2, these belows are counted as the samples
        expected = [4, 7]
        samples = script_base.take_samples(a_list, 3, 2)
        self.assertEqual(expected, samples)
        # At interval of 2 and length of 4, these belows are counted as the samples
        expected = [1, 3, 5, 7]
        samples = script_base.take_samples(a_list, 2, 4)
        self.assertEqual(expected, samples)
        # At interval of 2 and length of 1, these belows are counted as the samples
        expected = [7]
        samples = script_base.take_samples(a_list, 2, 1)
        self.assertEqual(expected, samples)

    def test_avg_and_median_mid_price_chg(self):
        script_base = ScriptBase()
        script_base.mid_prices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        avg_chg = script_base.avg_price_volatility(3, 10)
        # since there is not enough sample size, it should return None
        self.assertTrue(avg_chg is None)
        avg_chg = script_base.avg_price_volatility(3, 5)
        # at 5 sample size, as we need 5 +1, so this should also return None
        self.assertTrue(avg_chg is None)
        # At interval of 4 and length of 3, these belows are counted as the samples
        # The samples are 15, 11,  7, 3
        expected_chg = [(15 - 11) / 11, (11 - 7) / 7, (7 - 3) / 3]
        self.assertEqual(mean(expected_chg), script_base.avg_price_volatility(4, 3))
        # The median change is (11 - 7) / 7
        self.assertEqual((11 - 7) / 7, script_base.median_price_volatility(4, 3))

        # At 10 interval and length of 1.
        expected_chg = (15 - 5) / 5
        self.assertEqual(expected_chg, script_base.avg_price_volatility(10, 1))

    def test_round_by_step(self):
        self.assertEqual(Decimal("1.75"), ScriptBase.round_by_step(Decimal("1.8"), Decimal("0.25")))
        self.assertEqual(Decimal("1.75"), ScriptBase.round_by_step(Decimal("1.75"), Decimal("0.25")))
        self.assertEqual(Decimal("1.75"), ScriptBase.round_by_step(Decimal("1.7567"), Decimal("0.01")))
        self.assertEqual(Decimal("1"), ScriptBase.round_by_step(Decimal("1.7567"), Decimal("1")))
        self.assertEqual(Decimal("-1.75"), ScriptBase.round_by_step(Decimal("-1.8"), Decimal("0.25")))
