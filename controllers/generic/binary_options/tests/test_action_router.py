"""Tests for action_router.py."""
from unittest.mock import MagicMock

import pytest

from controllers.generic.binary_options.action_router import ActionRouter, ExecutionPath

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_routing_config(**overrides):
    """Return a mock ActionRoutingConfig with sensible defaults."""
    defaults = dict(
        entry_mode="limit",
        taker_edge_threshold=0.15,
        taker_time_threshold_min=5.0,
        mint_enabled=False,
        mint_min_spread=0.03,
        mint_prefer_over_buy=False,
        delta_neutral_enabled=False,
        delta_neutral_max_edge=0.03,
        delta_neutral_min_spread=0.02,
        require_signal_agreement=False,
        conflict_mode="veto",
        conflict_size_mult=0.5,
        position_size_mode="fixed",
        fixed_position_size=5.0,
        max_position_size=20.0,
        edge_size_multiplier=100.0,
        kelly_fraction=0.25,
        max_positions_per_coin=1,
        max_total_positions=5,
    )
    defaults.update(overrides)
    rc = MagicMock()
    for k, v in defaults.items():
        setattr(rc, k, v)
    return rc


def _make_position_tracker(can_open_result=(True, "")):
    pt = MagicMock()
    pt.can_open.return_value = can_open_result
    return pt


def _make_signal(**overrides):
    defaults = dict(
        direction="YES",
        edge=0.10,
        entry_price=0.45,
        slug="BTC-100k-UP",
        strike=100000,
        market_expiry_ts=9999999999.0,
        btc_spot=99000.0,
        spot_direction="UP",
        btc_direction="UP",
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# _select_path tests
# ---------------------------------------------------------------------------

class TestSelectPath:
    def _call(self, signal, market, rc, minutes_to_expiry):
        router = ActionRouter(rc, _make_position_tracker())
        return router._select_path(signal, market, rc, minutes_to_expiry)

    def test_default_limit_yes(self):
        rc = _make_routing_config()
        path = self._call(_make_signal(direction="YES", edge=0.05), {}, rc, 30.0)
        assert path == ExecutionPath.BUY_YES_LIMIT

    def test_default_limit_no(self):
        rc = _make_routing_config()
        path = self._call(_make_signal(direction="NO", edge=0.05), {}, rc, 30.0)
        assert path == ExecutionPath.BUY_NO_LIMIT

    def test_market_mode_override(self):
        rc = _make_routing_config(entry_mode="market")
        path = self._call(_make_signal(direction="YES"), {}, rc, 30.0)
        assert path == ExecutionPath.BUY_YES_MARKET

    def test_taker_edge_threshold(self):
        rc = _make_routing_config(taker_edge_threshold=0.10)
        path = self._call(_make_signal(direction="NO", edge=0.15), {}, rc, 30.0)
        assert path == ExecutionPath.BUY_NO_MARKET

    def test_taker_time_threshold(self):
        rc = _make_routing_config(taker_time_threshold_min=10.0)
        path = self._call(_make_signal(direction="YES", edge=0.01), {}, rc, 3.0)
        assert path == ExecutionPath.BUY_YES_MARKET

    def test_mint_prefer(self):
        rc = _make_routing_config(mint_enabled=True, mint_prefer_over_buy=True)
        assert self._call(_make_signal(direction="YES"), {}, rc, 30.0) == ExecutionPath.MINT_SELL_NO_LIMIT
        assert self._call(_make_signal(direction="NO"), {}, rc, 30.0) == ExecutionPath.MINT_SELL_YES_LIMIT

    def test_delta_neutral(self):
        rc = _make_routing_config(
            delta_neutral_enabled=True,
            delta_neutral_max_edge=0.05,
            delta_neutral_min_spread=0.01,
        )
        path = self._call(_make_signal(edge=0.02), {"spread": 0.03}, rc, 30.0)
        assert path == ExecutionPath.MINT_SELL_BOTH


# ---------------------------------------------------------------------------
# _check_conflict tests
# ---------------------------------------------------------------------------

class TestCheckConflict:
    def _call(self, signal, **rc_overrides):
        rc = _make_routing_config(**rc_overrides)
        router = ActionRouter(rc, _make_position_tracker())
        return router._check_conflict(signal)

    def test_no_agreement_required(self):
        ok, mult = self._call(_make_signal(spot_direction="UP", btc_direction="DOWN"),
                              require_signal_agreement=False)
        assert ok is True
        assert mult == 1.0

    def test_agreement_no_conflict(self):
        ok, mult = self._call(_make_signal(spot_direction="UP", btc_direction="UP"),
                              require_signal_agreement=True)
        assert ok is True
        assert mult == 1.0

    def test_veto_blocks(self):
        ok, mult = self._call(_make_signal(spot_direction="UP", btc_direction="DOWN"),
                              require_signal_agreement=True, conflict_mode="veto")
        assert ok is False

    def test_reduce_multiplies(self):
        ok, mult = self._call(_make_signal(spot_direction="UP", btc_direction="DOWN"),
                              require_signal_agreement=True, conflict_mode="reduce",
                              conflict_size_mult=0.3)
        assert ok is True
        assert mult == pytest.approx(0.3)

    def test_ignore_passes(self):
        ok, mult = self._call(_make_signal(spot_direction="UP", btc_direction="DOWN"),
                              require_signal_agreement=True, conflict_mode="ignore")
        assert ok is True
        assert mult == 1.0


# ---------------------------------------------------------------------------
# _compute_size tests
# ---------------------------------------------------------------------------

class TestComputeSize:
    def _call(self, signal, conflict_mult=1.0, **rc_overrides):
        rc = _make_routing_config(**rc_overrides)
        router = ActionRouter(rc, _make_position_tracker())
        return router._compute_size("BTC", signal, rc, conflict_mult)

    def test_fixed(self):
        size = self._call(_make_signal(edge=0.10), position_size_mode="fixed",
                          fixed_position_size=7.0)
        assert size == pytest.approx(7.0)

    def test_edge_scaled(self):
        size = self._call(_make_signal(edge=0.10), position_size_mode="edge_scaled",
                          edge_size_multiplier=100.0, max_position_size=20.0)
        assert size == pytest.approx(10.0)

    def test_edge_scaled_capped(self):
        size = self._call(_make_signal(edge=0.50), position_size_mode="edge_scaled",
                          edge_size_multiplier=100.0, max_position_size=20.0)
        assert size == pytest.approx(20.0)

    def test_kelly(self):
        # edge=0.10, entry_price=0.45, denom=0.55, kelly_fraction=0.25
        # size = (0.10 / 0.55) * 0.25 ≈ 0.04545
        size = self._call(_make_signal(edge=0.10, entry_price=0.45),
                          position_size_mode="kelly", kelly_fraction=0.25,
                          max_position_size=20.0)
        assert size == pytest.approx(0.10 / 0.55 * 0.25, rel=1e-4)

    def test_conflict_multiplier_applied(self):
        size = self._call(_make_signal(edge=0.10), conflict_mult=0.5,
                          position_size_mode="fixed", fixed_position_size=10.0)
        assert size == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# route() integration tests
# ---------------------------------------------------------------------------

class TestRoute:
    def test_full_pipeline(self):
        rc = _make_routing_config()
        pt = _make_position_tracker(can_open_result=(True, ""))
        router = ActionRouter(rc, pt)

        signals = {"BTC": _make_signal(direction="YES", edge=0.05)}
        market_data = {"BTC": {"spread": 0.05}}
        actions = router.route(signals, market_data, [], now_ts=1000.0)

        assert len(actions) == 1
        a = actions[0]
        assert a["coin"] == "BTC"
        assert a["direction"] == "YES"
        assert a["path"] == ExecutionPath.BUY_YES_LIMIT
        assert a["size"] == pytest.approx(5.0)

    def test_blocked_by_position_tracker(self):
        rc = _make_routing_config()
        pt = _make_position_tracker(can_open_result=(False, "max positions"))
        router = ActionRouter(rc, pt)

        signals = {"BTC": _make_signal()}
        actions = router.route(signals, {}, [], now_ts=1000.0)
        assert actions == []

    def test_multiple_coins(self):
        rc = _make_routing_config()
        pt = _make_position_tracker(can_open_result=(True, ""))
        router = ActionRouter(rc, pt)

        signals = {
            "BTC": _make_signal(direction="YES", edge=0.05),
            "ETH": _make_signal(direction="NO", edge=0.05),
        }
        actions = router.route(signals, {}, [], now_ts=1000.0)
        assert len(actions) == 2
        coins = {a["coin"] for a in actions}
        assert coins == {"BTC", "ETH"}
