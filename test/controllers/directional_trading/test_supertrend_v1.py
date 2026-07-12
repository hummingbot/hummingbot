from unittest import TestCase

import numpy as np
import pandas as pd

from controllers.directional_trading.supertrend_v1 import SuperTrend


class SuperTrendFeatureTest(TestCase):
    def test_calculated_features_do_not_contain_nan_values(self):
        closes = np.linspace(100, 120, 100)
        candles = pd.DataFrame({
            "timestamp": np.arange(100),
            "open": closes - 0.2,
            "high": closes + 0.5,
            "low": closes - 0.5,
            "close": closes,
            "volume": np.ones(100),
        })

        result = SuperTrend.calculate_features(candles, length=20, multiplier=4.0, percentage_threshold=0.01)

        self.assertFalse(result.isna().any().any())
        self.assertIn("signal", result.columns)
        self.assertTrue(set(result["signal"].unique()).issubset({-1, 0, 1}))
