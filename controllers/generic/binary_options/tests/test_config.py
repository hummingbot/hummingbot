"""Tests for config.py — BinaryOptionsController configuration and runtime bridge."""
import json
import math
import os

# Avoid importing hummingbot internals that pull in pandas/heavy deps.
# We mock ControllerConfigBase so tests run without the full hummingbot env.
import sys
import tempfile
import time
import unittest
from types import ModuleType
from unittest.mock import patch

# --- Stub hummingbot modules ---
_hb = ModuleType("hummingbot")
_hb_s = ModuleType("hummingbot.strategy_v2")
_hb_sc = ModuleType("hummingbot.strategy_v2.controllers")
_hb_scb = ModuleType("hummingbot.strategy_v2.controllers.controller_base")

from pydantic import BaseModel, ConfigDict, Field


class _StubControllerConfigBase(BaseModel):
    """Minimal stub matching ControllerConfigBase fields used by our config."""
    id: str = "test"
    controller_name: str = ""
    controller_type: str = "generic"
    total_amount_quote: float = 100.0
    model_config = ConfigDict(arbitrary_types_allowed=True)


_hb_scb.ControllerConfigBase = _StubControllerConfigBase  # type: ignore

sys.modules.setdefault("hummingbot", _hb)
sys.modules.setdefault("hummingbot.strategy_v2", _hb_s)
sys.modules.setdefault("hummingbot.strategy_v2.controllers", _hb_sc)
sys.modules.setdefault("hummingbot.strategy_v2.controllers.controller_base", _hb_scb)

# Now import our module
from controllers.generic.binary_options.config import (
    ActionRoutingConfig,
    BinaryOptionsControllerConfig,
    CoinRoster,
    RuntimeBridge,
)
from controllers.generic.binary_options.fair_value import halflife_to_alpha

_LN2 = math.log(2)


class TestActionRoutingConfig(unittest.TestCase):
    def test_defaults(self):
        r = ActionRoutingConfig()
        self.assertEqual(r.entry_mode, "limit")
        self.assertAlmostEqual(r.taker_edge_threshold, 0.15)
        self.assertAlmostEqual(r.taker_time_threshold_min, 5.0)
        self.assertFalse(r.mint_enabled)
        self.assertAlmostEqual(r.mint_min_spread, 0.03)
        self.assertFalse(r.mint_prefer_over_buy)
        self.assertFalse(r.delta_neutral_enabled)
        self.assertAlmostEqual(r.delta_neutral_max_edge, 0.03)
        self.assertAlmostEqual(r.delta_neutral_min_spread, 0.02)
        self.assertFalse(r.require_signal_agreement)
        self.assertEqual(r.conflict_mode, "veto")
        self.assertAlmostEqual(r.conflict_size_mult, 0.5)
        self.assertEqual(r.exit_mode, "limit")
        self.assertAlmostEqual(r.exit_taker_urgency_min, 2.0)
        self.assertTrue(r.hold_to_settlement)
        self.assertAlmostEqual(r.settlement_hold_threshold, 0.70)
        self.assertEqual(r.max_positions_per_coin, 1)
        self.assertEqual(r.max_total_positions, 5)
        self.assertEqual(r.position_size_mode, "fixed")
        self.assertAlmostEqual(r.fixed_position_size, 5.0)
        self.assertAlmostEqual(r.max_position_size, 20.0)
        self.assertAlmostEqual(r.edge_size_multiplier, 100.0)

    def test_custom_values(self):
        r = ActionRoutingConfig(entry_mode="auto", max_total_positions=10)
        self.assertEqual(r.entry_mode, "auto")
        self.assertEqual(r.max_total_positions, 10)


class TestBinaryOptionsControllerConfig(unittest.TestCase):
    def test_defaults(self):
        c = BinaryOptionsControllerConfig(
            runtime_json_path="/tmp/rt.json",
            config_json_path="/tmp/cfg.json",
        )
        self.assertEqual(c.controller_type, "generic")
        self.assertEqual(c.controller_name, "binary_options")
        self.assertEqual(c.connector_name, "limitless")
        self.assertEqual(c.poll_interval_ms, 1500)
        self.assertEqual(c.vol_warmup_ticks, 20)
        self.assertIsInstance(c.routing, ActionRoutingConfig)

    def test_custom(self):
        c = BinaryOptionsControllerConfig(
            runtime_json_path="/x",
            config_json_path="/y",
            poll_interval_ms=2000,
            total_amount_quote=500.0,
            routing=ActionRoutingConfig(entry_mode="market"),
        )
        self.assertEqual(c.poll_interval_ms, 2000)
        self.assertEqual(c.routing.entry_mode, "market")


class TestRuntimeBridge(unittest.TestCase):
    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self._path = self._tmpfile.name
        self._write({"trading_enabled": True, "paused": False, "coins": {}})

    def tearDown(self):
        os.unlink(self._path)

    def _write(self, data):
        with open(self._path, "w") as f:
            json.dump(data, f)

    def test_initial_load(self):
        rb = RuntimeBridge(self._path)
        self.assertTrue(rb.should_trade())

    def test_check_reload_on_mtime_change(self):
        rb = RuntimeBridge(self._path, check_interval=0.0)
        self.assertTrue(rb.should_trade())
        # Modify file
        self._write({"trading_enabled": False, "paused": False, "coins": {}})
        # Force mtime difference
        os.utime(self._path, (time.time() + 10, time.time() + 10))
        reloaded = rb.check()
        self.assertTrue(reloaded)
        self.assertFalse(rb.should_trade())

    def test_check_no_reload_within_interval(self):
        rb = RuntimeBridge(self._path, check_interval=9999.0)
        # Even after modifying, check() returns False due to interval
        self._write({"trading_enabled": False, "paused": False, "coins": {}})
        self.assertFalse(rb.check())

    def test_get_coin_param_resolution(self):
        self._write({
            "trading_enabled": True,
            "paused": False,
            "baseline_halflife_secs": 50.0,
            "coins": {
                "BTC": {"baseline_halflife_secs": 25.0},
                "ETH": {},
            },
        })
        rb = RuntimeBridge(self._path)
        # Coin-level override
        self.assertEqual(rb.get_coin_param("BTC", "baseline_halflife_secs", 35.0), 25.0)
        # Top-level fallback
        self.assertEqual(rb.get_coin_param("ETH", "baseline_halflife_secs", 35.0), 50.0)
        # Top-level fallback for unlisted coin (SOL not in coins, but top-level key exists)
        self.assertEqual(rb.get_coin_param("SOL", "baseline_halflife_secs", 35.0), 50.0)
        # True default fallback (key not in file at all)
        self.assertEqual(rb.get_coin_param("SOL", "nonexistent_key", 99.0), 99.0)

    def test_get_alphas(self):
        self._write({
            "trading_enabled": True, "paused": False,
            "coins": {"BTC": {
                "baseline_halflife_secs": 35.0,
                "current_halflife_secs": 12.0,
                "mispricing_halflife_secs": 23.0,
            }},
        })
        rb = RuntimeBridge(self._path)
        interval = 1.5
        bl, cur, mis = rb.get_alphas("BTC", interval)
        self.assertAlmostEqual(bl, halflife_to_alpha(35.0, 1.5))
        self.assertAlmostEqual(cur, halflife_to_alpha(12.0, 1.5))
        self.assertAlmostEqual(mis, halflife_to_alpha(23.0, 1.5))

    def test_should_trade_variations(self):
        for te, pa, expected in [
            (True, False, True),
            (True, True, False),
            (False, False, False),
            (False, True, False),
        ]:
            self._write({"trading_enabled": te, "paused": pa, "coins": {}})
            rb = RuntimeBridge(self._path)
            self.assertEqual(rb.should_trade(), expected, f"te={te} pa={pa}")

    def test_overrides(self):
        self._write({
            "trading_enabled": True, "paused": False,
            "coins": {"X": {}}, "_meta": {"v": 1},
            "custom_key": 42,
        })
        rb = RuntimeBridge(self._path)
        ov = rb.overrides
        self.assertIn("custom_key", ov)
        self.assertNotIn("coins", ov)
        self.assertNotIn("_meta", ov)


class TestCoinRoster(unittest.TestCase):
    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self._path = self._tmpfile.name
        data = {
            "trading_enabled": True, "paused": False,
            "coins": {
                "BTC": {"tier": "MAIN"},
                "DOGE": {"tier": "BANNED"},
                "SHIB": {"tier": "REHAB"},
                "SOL": {"tier": "PROBATION"},
            },
        }
        with open(self._path, "w") as f:
            json.dump(data, f)
        self._rb = RuntimeBridge(self._path)

    def tearDown(self):
        os.unlink(self._path)

    def test_tier_known(self):
        cr = CoinRoster(self._rb)
        self.assertEqual(cr.tier("BTC"), "MAIN")
        self.assertEqual(cr.tier("DOGE"), "BANNED")

    def test_tier_unknown_defaults_main(self):
        cr = CoinRoster(self._rb)
        self.assertEqual(cr.tier("UNKNOWN"), "MAIN")

    def test_size_multiplier(self):
        cr = CoinRoster(self._rb)
        self.assertAlmostEqual(cr.size_multiplier("BTC"), 1.0)
        self.assertAlmostEqual(cr.size_multiplier("DOGE"), 0.0)
        self.assertAlmostEqual(cr.size_multiplier("SHIB"), 0.5)
        self.assertAlmostEqual(cr.size_multiplier("SOL"), 0.75)
        # Unknown coin → MAIN → 1.0
        self.assertAlmostEqual(cr.size_multiplier("UNKNOWN"), 1.0)

    def test_ensure_listed_noop(self):
        cr = CoinRoster(self._rb)
        cr.ensure_listed("BTC")  # should not raise


if __name__ == "__main__":
    unittest.main()
