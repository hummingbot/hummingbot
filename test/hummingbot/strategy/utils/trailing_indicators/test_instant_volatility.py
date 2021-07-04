import unittest
import numpy as np
from hummingbot.strategy.__utils__.trailing_indicators.instant_volatility import InstantVolatilityIndicator


class InstantVolatilityTest(unittest.TestCase):
    INITIAL_RANDOM_SEED = 3141592653
    BUFFER_LENGTH = 10000

    def setUp(self) -> None:
        np.random.seed(self.INITIAL_RANDOM_SEED)

    def test_calculate_volatility_without_smoothing(self):
        original_price = 100
        volatility = 0.1
        samples = np.random.normal(original_price, volatility * original_price, self.BUFFER_LENGTH)
        self.indicator = InstantVolatilityIndicator(self.BUFFER_LENGTH, 1)

        for sample in samples:
            self.indicator.add_sample(sample)

        self.assertAlmostEqual(self.indicator.current_value, volatility * original_price, 1)

    def test_calculate_volatility_with_smoothing(self):
        original_price = 100
        volatility = 0.1
        samples = np.random.normal(original_price, volatility * original_price, self.BUFFER_LENGTH)
        self.indicator = InstantVolatilityIndicator(self.BUFFER_LENGTH, 20)

        for sample in samples:
            self.indicator.add_sample(sample)

        self.assertAlmostEqual(self.indicator.current_value, volatility * original_price, 1)

    def test_compare_volatility_with_smoothing(self):
        original_price = 100
        volatility = 0.1
        # This time I'm creating 10 times the buffer length
        samples = np.random.normal(original_price, volatility * original_price, self.BUFFER_LENGTH)
        self.indicator_normal = InstantVolatilityIndicator(self.BUFFER_LENGTH, 1)
        # Using 20 samples of smoothing
        self.indicator_smoothed = InstantVolatilityIndicator(self.BUFFER_LENGTH, 20)

        output_normal = []
        output_smoothed = []
        for sample in samples:
            self.indicator_normal.add_sample(sample)
            self.indicator_smoothed.add_sample(sample)
            output_normal.append(self.indicator_normal.current_value)
            output_smoothed.append(self.indicator_smoothed.current_value)

        # Now we want to assert output from smoothed indicator is more "smoothed" than normal one.
        # How do we do this? By measuring the energy of the first derivative of each output.
        # Energy(diff) = Sum(diff(output)**2)

        energy_normal = sum(x ** 2 for x in np.diff(output_normal))
        energy_smoothed = sum(x ** 2 for x in np.diff(output_smoothed))

        self.assertGreater(energy_normal, energy_smoothed)
