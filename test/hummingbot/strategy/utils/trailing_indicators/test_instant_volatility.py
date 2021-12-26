import unittest
import numpy as np
from hummingbot.strategy.__utils__.trailing_indicators.instant_volatility import InstantVolatilityIndicator


class InstantVolatilityTest(unittest.TestCase):
    INITIAL_RANDOM_SEED = 3141592653
    BUFFER_LENGTH = 10000

    def setUp(self) -> None:
        np.random.seed(self.INITIAL_RANDOM_SEED)

    def test_calculate_volatility(self):
        original_price = 100
        volatility = 0.1
        samples = np.random.normal(original_price, volatility * original_price, self.BUFFER_LENGTH)
        self.indicator = InstantVolatilityIndicator(self.BUFFER_LENGTH, 1)

        for sample in samples:
            self.indicator.add_sample(sample)

        self.assertAlmostEqual(self.indicator.current_value, 14.06933307647705, 4)
