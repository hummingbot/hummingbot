"""Tests for signal_engine.py"""
import copy
import json
import math
import os
import sys
import tempfile
import types
import unittest

# Stub out hummingbot imports before importing config
# config.py imports from hummingbot.strategy_v2 which needs pandas etc.
_hb_stub = types.ModuleType("hummingbot")
_hb_stub.strategy_v2 = types.ModuleType("hummingbot.strategy_v2")
_hb_stub.strategy_v2.controllers = types.ModuleType("hummingbot.strategy_v2.controllers")


class _FakeControllerConfigBase:
    pass


_ctrl_base_mod = types.ModuleType("hummingbot.strategy_v2.controllers.controller_base")
_ctrl_base_mod.ControllerConfigBase = _FakeControllerConfigBase
_hb_stub.strategy_v2.controllers.controller_base = _ctrl_base_mod

sys.modules.setdefault("hummingbot", _hb_stub)
sys.modules.setdefault("hummingbot.strategy_v2", _hb_stub.strategy_v2)
sys.modules.setdefault("hummingbot.strategy_v2.controllers", _hb_stub.strategy_v2.controllers)
sys.modules.setdefault("hummingbot.strategy_v2.controllers.controller_base", _ctrl_base_mod)

from controllers.generic.binary_options.config import RuntimeBridge
from controllers.generic.binary_options.signal_engine import (
    CoinProfile,
    DynamicThresholds,
    EMALayer,
    OpenSignal,
    SignalEngine,
    TypeStats,
    _check_hour_boundary,
    _ema,
    _ema_var,
    _feed_lag,
    _logit,
    compute_confidence,
    lag_z_score,
    merged_lag_rate,
)


def _make_runtime(tmp_dir, data=None):
    """Create a minimal runtime.json and return RuntimeBridge."""
    if data is None:
        data = {"trading_enabled": True, "paused": False}
    path = os.path.join(tmp_dir, "runtime.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return RuntimeBridge(path)


def _make_engine(tmp_dir, config_overrides=None):
    config = {
        "poll_interval_ms": 1000,
        "min_btc_delta": 10.0,
        "min_coin_delta": 0.005,
        "dyn_thresh_min_samples": 3,
        "edge_min_history_secs": 5,
        "edge_min_vol_obs_secs": 5,
    }
    if config_overrides:
        config.update(config_overrides)
    rb = _make_runtime(tmp_dir)
    return SignalEngine(config, rb)


class TestEma(unittest.TestCase):
    def test_seed(self):
        self.assertEqual(_ema(999.0, 5.0, 0.1, 0), 5.0)

    def test_standard_update(self):
        result = _ema(10.0, 20.0, 0.3, 5)
        self.assertAlmostEqual(result, 0.3 * 20 + 0.7 * 10)

    def test_ema_var(self):
        v = _ema_var(1.0, 2.0, 0.1)
        # (1-0.1)*(1.0 + 0.1*4) = 0.9*1.4 = 1.26
        self.assertAlmostEqual(v, 1.26)


class TestDynamicThresholds(unittest.TestCase):
    def test_adapts(self):
        dt = DynamicThresholds(10.0, 0.005, window=10, multiplier=1.5,
                               min_samples=3, floor_pct=0.3)
        # Feed enough data
        for i in range(5):
            dt.feed(float(i * 5), {"ETH": i * 0.01})
        self.assertNotEqual(dt.btc_threshold, 10.0)

    def test_floor_enforced(self):
        dt = DynamicThresholds(10.0, 0.005, window=10, multiplier=1.5,
                               min_samples=3, floor_pct=0.3)
        # Feed tiny deltas — threshold should hit floor
        for _ in range(5):
            dt.feed(0.001, {"ETH": 0.00001})
        self.assertGreaterEqual(dt.btc_threshold, 10.0 * 0.3)
        self.assertGreaterEqual(dt.get_coin_threshold("ETH"), 0.005 * 0.3)


class TestEventClassification(unittest.TestCase):
    def test_type1_btc_moved_coin_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_engine(tmp, {"dyn_thresh_min_samples": 100})
            markets = {"ETH": {"yes_price": 0.5, "strike": 3000, "hours_left": 0.5}}
            # Tick 1: seed
            engine.tick({"ETH": 3000}, markets, 60000, 1.0)
            # Tick 2: BTC moves, coin flat
            result = engine.tick({"ETH": 3000}, {"ETH": {"yes_price": 0.5, "strike": 3000, "hours_left": 0.5}},
                                  60020, 2.0)
            self.assertEqual(result["ETH"]["event_type"], 1)

    def test_type2_both_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_engine(tmp, {"dyn_thresh_min_samples": 100})
            markets = {"ETH": {"yes_price": 0.5, "strike": 3000, "hours_left": 0.5}}
            engine.tick({"ETH": 3000}, markets, 60000, 1.0)
            result = engine.tick({"ETH": 3000},
                                  {"ETH": {"yes_price": 0.51, "strike": 3000, "hours_left": 0.5}},
                                  60020, 2.0)
            self.assertEqual(result["ETH"]["event_type"], 2)

    def test_type3_coin_moved_btc_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_engine(tmp, {"dyn_thresh_min_samples": 100})
            markets = {"ETH": {"yes_price": 0.5, "strike": 3000, "hours_left": 0.5}}
            engine.tick({"ETH": 3000}, markets, 60000, 1.0)
            result = engine.tick({"ETH": 3000},
                                  {"ETH": {"yes_price": 0.51, "strike": 3000, "hours_left": 0.5}},
                                  60000, 2.0)  # BTC unchanged
            self.assertEqual(result["ETH"]["event_type"], 3)


class TestMergedLagRate(unittest.TestCase):
    def test_three_layer_merge(self):
        prof = CoinProfile()
        prof.baseline.lag_rate = 0.6
        prof.baseline.btc_move_seen = 20
        prof.last_hour.lag_rate = 0.4
        prof.last_hour.btc_move_seen = 5
        prof.current.lag_rate = 0.8
        prof.current.btc_move_seen = 5

        result = merged_lag_rate(prof, [0.5, 0.3, 0.2], min_events_curr=3)
        expected = 0.5 * 0.6 + 0.3 * 0.4 + 0.2 * 0.8
        self.assertAlmostEqual(result, expected)

    def test_graceful_degradation(self):
        prof = CoinProfile()
        prof.baseline.lag_rate = 0.6
        prof.baseline.btc_move_seen = 20
        # current has no events
        result = merged_lag_rate(prof, [0.5, 0.3, 0.2], min_events_curr=3)
        self.assertAlmostEqual(result, 0.6)


class TestLagZScore(unittest.TestCase):
    def test_logit_space(self):
        prof = CoinProfile()
        prof.baseline.lag_rate = 0.3
        prof.baseline.btc_move_seen = 20
        prof.current.lag_rate = 0.7
        prof.current.btc_move_seen = 5

        z = lag_z_score(prof, [0.5, 0.3, 0.2], min_events_curr=3, min_var_obs=10)
        expected = _logit(0.7) - _logit(0.3)
        self.assertAlmostEqual(z, expected)

    def test_insufficient_obs(self):
        prof = CoinProfile()
        prof.baseline.btc_move_seen = 5
        z = lag_z_score(prof, [0.5, 0.3, 0.2], min_events_curr=3, min_var_obs=10)
        self.assertEqual(z, 0.0)


class TestHourBoundary(unittest.TestCase):
    def test_rotation(self):
        prof = CoinProfile()
        prof.current.lag_rate = 0.7
        prof.current.btc_move_seen = 10
        prof.hour_started = 5

        profiles = {"ETH": prof}
        _check_hour_boundary(profiles, 6)

        self.assertAlmostEqual(prof.last_hour.lag_rate, 0.7)
        self.assertEqual(prof.current.btc_move_seen, 0)
        self.assertEqual(prof.hour_started, 6)


class TestSignalEngineTick(unittest.TestCase):
    def test_tick_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_engine(tmp)
            markets = {"ETH": {"yes_price": 0.5, "strike": 3000, "hours_left": 0.5}}
            spots = {"ETH": 3000.0}

            # Multiple ticks
            for i in range(5):
                result = engine.tick(spots, markets, 60000 + i * 10, float(i))

            self.assertIn("ETH", result)
            sig = result["ETH"]
            for key in ["spot_signal", "btc_signal", "direction", "edge",
                        "z_score", "btc_z_score", "entry_path", "confidence"]:
                self.assertIn(key, sig)


class TestDualScoreEntry(unittest.TestCase):
    def test_spot_path(self):
        """Feed enough data for spot mispricing to fire."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_engine(tmp, {
                "edge_min_history_secs": 2,
                "edge_min_vol_obs_secs": 2,
                "entry_path_priority": ["SPOT", "BTC", "COMBINED"],
            })
            # Feed many ticks with varying spot to build vol
            base_spot = 3000.0
            for i in range(30):
                spot = base_spot + (i % 5) * 10 - 20
                yes = 0.5 + (0.01 if i % 3 == 0 else -0.01)
                markets = {"ETH": {"yes_price": yes, "strike": 3000, "hours_left": 0.5}}
                result = engine.tick({"ETH": spot}, markets, 60000, float(i))

            # Check structure is valid
            self.assertIn("ETH", result)
            self.assertIn("entry_path", result["ETH"])

    def test_combined_path(self):
        """Verify COMBINED path structure exists."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_engine(tmp)
            markets = {"ETH": {"yes_price": 0.5, "strike": 3000, "hours_left": 0.5}}
            result = engine.tick({"ETH": 3000}, markets, 60000, 1.0)
            # First tick won't fire, just verify structure
            self.assertIsNone(result["ETH"]["entry_path"])


class TestConfidence(unittest.TestCase):
    def test_high_when_layers_agree(self):
        prof = CoinProfile()
        prof.baseline.lag_rate = 0.5
        prof.baseline.btc_move_seen = 20
        prof.last_hour.lag_rate = 0.52
        prof.last_hour.btc_move_seen = 5
        prof.current.lag_rate = 0.48
        prof.current.btc_move_seen = 5
        self.assertEqual(compute_confidence(prof, 0.25, 3), "HIGH")

    def test_low_when_layers_diverge(self):
        prof = CoinProfile()
        prof.baseline.lag_rate = 0.2
        prof.baseline.btc_move_seen = 20
        prof.current.lag_rate = 0.8
        prof.current.btc_move_seen = 5
        self.assertEqual(compute_confidence(prof, 0.25, 3), "LOW")


if __name__ == "__main__":
    unittest.main()
