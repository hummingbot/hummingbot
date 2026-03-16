"""Tests for PositionTracker."""

from unittest.mock import MagicMock

import pytest


def _make_config(max_total=5, max_per_coin=1):
    config = MagicMock()
    config.routing.max_total_positions = max_total
    config.routing.max_positions_per_coin = max_per_coin
    return config


def _make_rb(overrides=None):
    """Mock RuntimeBridge with configurable per-coin params."""
    defaults = {
        "cooldown": 10.0,
        "streak_threshold": 5,
        "streak_pause_secs": 300,
        "cb_max_losses": 10,
        "cb_window_secs": 3600,
        "min_position_size": 1.0,
        "min_edge_entry_price": 0.15,
        "max_edge_entry_price": 0.99,
    }
    if overrides:
        defaults.update(overrides)
    rb = MagicMock()
    rb.get_coin_param = MagicMock(side_effect=lambda coin, key, default=None: defaults.get(key, default))
    return rb


def _make_tracker(**kwargs):
    from controllers.generic.binary_options.position_tracker import PositionTracker
    config = kwargs.pop("config", _make_config())
    rb = kwargs.pop("rb", _make_rb())
    return PositionTracker(config, rb)


class TestCanOpen:
    def test_passes_no_constraints(self):
        t = _make_tracker()
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=1000.0)
        assert ok is True
        assert reason == ""

    def test_blocked_max_total_positions(self):
        t = _make_tracker(config=_make_config(max_total=2))
        t.record_open("BTC", "e1", "YES", 5.0, now_ts=100)
        t.record_open("ETH", "e2", "YES", 5.0, now_ts=100)
        ok, reason = t.can_open("SOL", "YES", 5.0, now_ts=200)
        assert ok is False
        assert "max_total_positions" in reason

    def test_blocked_max_positions_per_coin(self):
        t = _make_tracker(config=_make_config(max_per_coin=1))
        t.record_open("BTC", "e1", "YES", 5.0, now_ts=100)
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=200)
        assert ok is False
        assert "max_positions_per_coin" in reason

    def test_blocked_by_cooldown(self):
        t = _make_tracker(rb=_make_rb({"cooldown": 10.0}))
        t.record_open("BTC", "e1", "YES", 5.0, now_ts=100)
        t.record_close("BTC", "e1", 1.0, now_ts=105)
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=110)
        assert ok is False
        assert "cooldown" in reason

    def test_allowed_after_cooldown(self):
        t = _make_tracker(rb=_make_rb({"cooldown": 10.0}))
        t.record_open("BTC", "e1", "YES", 5.0, now_ts=100)
        t.record_close("BTC", "e1", 1.0, now_ts=105)
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=116)
        assert ok is True

    def test_blocked_by_loss_streak(self):
        t = _make_tracker(rb=_make_rb({"streak_threshold": 3, "streak_pause_secs": 300, "cooldown": 0}))
        for i in range(3):
            t.record_open("BTC", f"e{i}", "YES", 5.0, now_ts=100 + i * 2)
            t.record_close("BTC", f"e{i}", -1.0, now_ts=101 + i * 2)
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=110)
        assert ok is False
        assert "streak" in reason

    def test_streak_resets_on_win(self):
        t = _make_tracker(rb=_make_rb({"streak_threshold": 3, "streak_pause_secs": 300, "cooldown": 0}))
        for i in range(2):
            t.record_open("BTC", f"e{i}", "YES", 5.0, now_ts=100 + i * 2)
            t.record_close("BTC", f"e{i}", -1.0, now_ts=101 + i * 2)
        # Win resets streak
        t.record_open("BTC", "ewin", "YES", 5.0, now_ts=110)
        t.record_close("BTC", "ewin", 2.0, now_ts=111)
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=112)
        assert ok is True

    def test_blocked_by_circuit_breaker(self):
        t = _make_tracker(rb=_make_rb({"cb_max_losses": 3, "cb_window_secs": 100, "cooldown": 0}))
        for i in range(3):
            t.record_open("BTC", f"e{i}", "YES", 5.0, now_ts=100 + i)
            t.record_close("BTC", f"e{i}", -1.0, now_ts=100 + i + 0.5)
        ok, reason = t.can_open("ETH", "YES", 5.0, now_ts=105)
        assert ok is False
        assert "circuit breaker" in reason

    def test_blocked_min_size(self):
        t = _make_tracker(rb=_make_rb({"min_position_size": 5.0}))
        ok, reason = t.can_open("BTC", "YES", 2.0, now_ts=100)
        assert ok is False
        assert "min_position_size" in reason

    def test_blocked_yes_price_range(self):
        t = _make_tracker()
        ok, reason = t.can_open("BTC", "YES", 5.0, now_ts=100, yes_price=0.05)
        assert ok is False
        assert "yes_price" in reason


class TestRecordAndProperties:
    def test_record_open_close(self):
        t = _make_tracker()
        t.record_open("BTC", "e1", "YES", 10.0, now_ts=100)
        assert t.open_count == 1
        assert t.total_exposure == 10.0
        assert t.positions_for_coin("BTC") == 1

        t.record_close("BTC", "e1", 2.0, now_ts=200)
        assert t.open_count == 0
        assert t.total_exposure == 0.0

    def test_multiple_positions(self):
        t = _make_tracker(config=_make_config(max_total=10, max_per_coin=5))
        t.record_open("BTC", "e1", "YES", 10.0, now_ts=100)
        t.record_open("BTC", "e2", "NO", 5.0, now_ts=101)
        t.record_open("ETH", "e3", "YES", 3.0, now_ts=102)
        assert t.open_count == 3
        assert t.total_exposure == 18.0
        assert t.positions_for_coin("BTC") == 2
        assert t.positions_for_coin("ETH") == 1

    def test_trade_count(self):
        t = _make_tracker()
        t.record_open("BTC", "e1", "YES", 5.0, now_ts=100)
        t.record_open("BTC", "e2", "YES", 5.0, now_ts=101)
        assert t._coin_trade_count["BTC"] == 2
