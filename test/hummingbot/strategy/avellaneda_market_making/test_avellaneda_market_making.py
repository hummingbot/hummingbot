import unittest
import numpy as np
from hummingbot.strategy.__utils__.trailing_indicators.average_volatility import AverageVolatilityIndicator

class MyTestCase(unittest.TestCase):
    def test_something(self):
        N_SAMPLES = 1000
        BUFFER_SIZE = 100
        INITIAL_RANDOM_SEED = 3141592653
        original_price = 100
        volatility = 0.005       # 0.5% of volatility (If asset is liquid, this is quite high!)
        np.random.seed(INITIAL_RANDOM_SEED)     # Using this hardcoded random seed we guarantee random samples generated are always the same
        samples = np.random.normal(original_price, volatility * original_price, N_SAMPLES)

        '''
        Idea is that this samples created guarantee the volatility is going to be the one you want.
        I'm testing the indicator volatility, but you could actually fix the rest of the parameters by fixing the samples.
        You can then change the volatility to be approximately equal to what you need. In this case ~0.5%
        '''
        volatility_indicator = AverageVolatilityIndicator(BUFFER_SIZE, 1) # This replicates the same indicator Avellaneda uses if volatility_buffer_samples = 100

        for sample in samples:
            volatility_indicator.add_sample(sample)

        self.assertEqual(volatility_indicator.current_value, 0.5018627218927454)

