import unittest
from decimal import Decimal

from hummingbot.strategy_v2.utils.distributions import Distributions


class TestDistributions(unittest.TestCase):

    def test_linear(self):
        result = Distributions.linear(5, 0, 10)
        expected = [Decimal(x) for x in [0, 2.5, 5, 7.5, 10]]
        self.assertEqual(result, expected)

    def test_linear_single_level(self):
        result = Distributions.linear(1, 0.5, 1)
        expected = [Decimal("0.5")]
        for r, e in zip(result, expected):
            self.assertAlmostEqual(r, e, places=2)

    def test_fibonacci(self):
        result = Distributions.fibonacci(5, 0.01)
        expected = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.05"), Decimal("0.08")]
        for r, e in zip(result, expected):
            self.assertAlmostEqual(r, e, places=2)

    def test_fibonacci_single_level(self):
        result = Distributions.fibonacci(1, 0.01)
        expected = [Decimal("0.01")]
        for r, e in zip(result, expected):
            self.assertAlmostEqual(r, e, places=2)

    def test_logarithmic(self):
        result = Distributions.logarithmic(4)
        # Expected values can be computed using the formula, but here are approximated:
        expected = [Decimal(x) for x in [0.4, 0.805, 1.093, 1.316]]
        for r, e in zip(result, expected):
            self.assertAlmostEqual(r, e, places=2)

    def test_arithmetic(self):
        result = Distributions.arithmetic(5, 1, 2)
        expected = [Decimal(x) for x in [1, 3, 5, 7, 9]]
        self.assertEqual(result, expected)

    def test_geometric(self):
        result = Distributions.geometric(5, 1, 2)
        expected = [Decimal(x) for x in [1, 2, 4, 8, 16]]
        self.assertEqual(result, expected)

    def test_geometric_invalid_ratio(self):
        with self.assertRaises(ValueError):
            Distributions.geometric(5, 1, 0.5)
