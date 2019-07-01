import math
import unittest

from hummingbot.client.performance_analysis import PerformanceAnalysis


class TestPerformanceAnalysis(unittest.TestCase):

    def test_basic_one_ex(self):
        """ Test performance analysis on a one exchange balance. """
        performance_analysis = PerformanceAnalysis()
        performance_analysis.add_balances("WETH", 0.5, True, True)
        performance_analysis.add_balances("DAI", 60, False, True)
        performance_analysis.add_balances("WETH", 0.4, True, False)
        performance_analysis.add_balances("DAI", 70, False, False)
        calculated_percent = performance_analysis.compute_profitability(50)
        expected_percent = (((0.4 * 50) + 70)/((0.5 * 50) + 60) - 1) * 100
        self.assertEqual(calculated_percent, expected_percent, "Basic one ex test failed.")

    def test_basic_two_ex(self):
        """ Test performance analysis on a two exchange balance with the same currencies trading in both exchanges. """
        performance_analysis = PerformanceAnalysis()
        performance_analysis.add_balances("WETH", 0.5, True, True)
        performance_analysis.add_balances("DAI", 60, False, True)
        performance_analysis.add_balances("WETH", 0.7, True, True)
        performance_analysis.add_balances("DAI", 50, False, True)
        performance_analysis.add_balances("WETH", 0.4, True, False)
        performance_analysis.add_balances("DAI", 70, False, False)
        performance_analysis.add_balances("WETH", 0.3, True, False)
        performance_analysis.add_balances("DAI", 70, False, False)
        calculated_percent = performance_analysis.compute_profitability(50)
        expected_percent = (((0.7 * 50) + 140)/((1.2 * 50) + 110) - 1) * 100
        self.assertEqual(calculated_percent, expected_percent, "Basic one ex test failed.")

    def test_different_tokens_two_ex(self):
        """ Test performance analysis on a two exchange balance with different currencies trading. Note that this test
        will not work as the config file that contains the conversion has not been loaded."""
        performance_analysis = PerformanceAnalysis()
        performance_analysis.add_balances("WETH", 0.5, True, True)
        performance_analysis.add_balances("DAI", 60, False, True)
        performance_analysis.add_balances("ETH", 0.7, True, True)
        performance_analysis.add_balances("USD", 50, False, True)
        performance_analysis.add_balances("WETH", 0.4, True, False)
        performance_analysis.add_balances("DAI", 70, False, False)
        performance_analysis.add_balances("ETH", 0.3, True, False)
        performance_analysis.add_balances("USD", 70, False, False)
        calculated_percent = performance_analysis.compute_profitability(50)
        expected_percent = (((0.7 * 50) + 140)/((1.2 * 50) + 110) - 1) * 100
        self.assertAlmostEquals(calculated_percent, expected_percent, msg="Two diff token test failed.", delta=0.1)

    def test_nan_starting(self):
        """ Test the case where the starting balance is 0. """
        performance_analysis = PerformanceAnalysis()
        performance_analysis.add_balances("WETH", 0, True, True)
        performance_analysis.add_balances("DAI", 0, False, True)
        performance_analysis.add_balances("WETH", 0.3, True, False)
        performance_analysis.add_balances("DAI", 70, False, False)
        calculated_percent = performance_analysis.compute_profitability(50)
        self.assertTrue(math.isnan(calculated_percent), "Starting value of 0 test failed.")


if __name__ == "__main__":
    unittest.main()
