import unittest
from decimal import Decimal
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.strategy.__utils__.trailing_indicators.historical_volatility import HistoricalVolatilityIndicator


class HistoricalVolatilityIndicatorUnitTest(unittest.TestCase):

    def test_historical_volatility(self):
        """
        test the historical volatility calculation
        """

        samples = [147.82, 149.5, 149.78, 149.86, 149.93, 150.89, 152.39, 153.74, 152.79, 151.23, 151.78]

        historical_volatility = HistoricalVolatilityIndicator(len(samples), len(samples) - 1)

        for sample in samples:
            historical_volatility.add_sample(sample)

        # test add_sample
        self.assertEqual(PerformanceMetrics.smart_round(Decimal(str(historical_volatility._sampling_buffer.get_last_value()))),
                         PerformanceMetrics.smart_round(Decimal(str(samples[-1]))))

        # test indicator calcluation
        self.assertEqual(PerformanceMetrics.smart_round(Decimal(str(historical_volatility._processing_buffer.get_last_value()))),
                         PerformanceMetrics.smart_round((Decimal(str(samples[-1])) / Decimal(str(samples[-2]))) - 1))

        # test historical_volatility calcluation
        self.assertEqual(PerformanceMetrics.smart_round(Decimal(str(historical_volatility.current_value))),
                         PerformanceMetrics.smart_round(Decimal("0.006602295840346792")))
        # self.assertEqual(historical_volatility.current_value, 0.006959421377874)
