import unittest
import numpy as np
from hummingbot.strategy.__utils__.trailing_indicators.historical_volatility import HistoricalVolatilityIndicator


class HistoricalVolatilityTest(unittest.TestCase):
    INITIAL_RANDOM_SEED = 123456789
    BUFFER_LENGTH = 1000

    def setUp(self) -> None:
        np.random.seed(self.INITIAL_RANDOM_SEED)

    def test_calculate_volatility_without_smoothing(self):
        original_price = 100
        volatility = 0.1
        returns = np.random.normal(0, volatility, self.BUFFER_LENGTH - 1)
        samples = [original_price]
        for r in returns:
            samples.append(samples[-1] * np.exp(r))
        self.indicator = HistoricalVolatilityIndicator(self.BUFFER_LENGTH, 1)

        for sample in samples:
            self.indicator.add_sample(sample)

        self.assertAlmostEqual(self.indicator.current_value * original_price, volatility * original_price, 0)

    def test_calculate_volatility_with_smoothing(self):
        original_price = 100
        volatility = 0.1
        returns = np.random.normal(0, volatility, self.BUFFER_LENGTH - 1)
        samples = [original_price]
        for r in returns:
            samples.append(samples[-1] * np.exp(r))
        self.indicator = HistoricalVolatilityIndicator(self.BUFFER_LENGTH, 20)

        for sample in samples:
            self.indicator.add_sample(sample)

        self.assertAlmostEqual(self.indicator.current_value * original_price, volatility * original_price, 0)

    def test_compare_volatility_with_smoothing(self):
        original_price = 100
        volatility = 0.1
        returns = np.random.normal(0, volatility, self.BUFFER_LENGTH - 1)
        samples = [original_price]
        for r in returns:
            samples.append(samples[-1] * np.exp(r))
        self.indicator_normal = HistoricalVolatilityIndicator(self.BUFFER_LENGTH, 1)
        # Using 20 samples of smoothing
        self.indicator_smoothed = HistoricalVolatilityIndicator(self.BUFFER_LENGTH, 20)

        output_normal = []
        output_smoothed = []
        for sample in samples:
            self.indicator_normal.add_sample(sample)
            self.indicator_smoothed.add_sample(sample)
            if self.indicator_normal.is_processing_buffer_full and self.indicator_smoothed.is_processing_buffer_full:
                output_normal.append(self.indicator_normal.current_value)
                output_smoothed.append(self.indicator_smoothed.current_value)

        # Now we want to assert output from smoothed indicator is more "smoothed" than normal one.
        # How do we do this? By measuring the energy of the first derivative of each output.
        # Energy(diff) = Sum(diff(output)**2)

        energy_normal = sum(x ** 2 for x in np.diff(output_normal))
        energy_smoothed = sum(x ** 2 for x in np.diff(output_smoothed))

        self.assertGreater(energy_normal, energy_smoothed)
