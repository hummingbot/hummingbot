from unittest import TestCase

import pandas as pd

from hummingbot.strategy_v2.routers.data_types import MarketRegime
from hummingbot.strategy_v2.routers.feature_engine import RouterFeatureEngine
from hummingbot.strategy_v2.routers.router import RuleBasedRouterThresholds, RuleBasedStrategyRouter


class RouterFeatureEngineTest(TestCase):
    @staticmethod
    def _candles(last_close: float, last_high: float, last_low: float) -> pd.DataFrame:
        return pd.DataFrame({
            "close": [100.0] * 50 + [last_close],
            "high": [100.5] * 50 + [last_high],
            "low": [99.5] * 50 + [last_low],
            "volume": [1.0] * 51,
        })

    def _decision(self, candles: pd.DataFrame):
        features = RouterFeatureEngine.build_features(
            candles=candles,
            active_executors=[],
            timestamp=1,
            range_length=50,
        )
        router = RuleBasedStrategyRouter(registry={}, thresholds=RuleBasedRouterThresholds())
        return features, router.decide(features)

    def test_detects_breakout_above_previous_range(self):
        features, decision = self._decision(self._candles(last_close=102.0, last_high=102.5, last_low=101.5))

        self.assertEqual(features.range_high, 100.5)
        self.assertEqual(decision.regime, MarketRegime.BREAKOUT_UP)

    def test_detects_breakout_below_previous_range(self):
        features, decision = self._decision(self._candles(last_close=98.0, last_high=98.5, last_low=97.5))

        self.assertEqual(features.range_low, 99.5)
        self.assertEqual(decision.regime, MarketRegime.BREAKOUT_DOWN)
