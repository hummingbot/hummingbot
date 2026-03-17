"""Tests for quote_manager.py"""
from unittest.mock import MagicMock

from controllers.generic.binary_options.config import QuoteConfig
from controllers.generic.binary_options.quote_manager import QuoteManager, QuoteState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_bridge(coin_params=None, global_params=None):
    """Create a mock RuntimeBridge."""
    _coin_params = coin_params or {}
    _global_params = global_params or {}
    bridge = MagicMock()

    def get_coin_param(coin, key, default=None):
        cp = _coin_params.get(coin, {})
        if key in cp:
            return cp[key]
        if key in _global_params:
            return _global_params[key]
        return default

    bridge.get_coin_param = get_coin_param
    return bridge


def make_signal(model_prob=0.5, z_score=0.0, btc_z_score=0.0, combined_z=0.0, yes_price=None):
    sig = {
        "model_prob": model_prob,
        "z_score": z_score,
        "btc_z_score": btc_z_score,
        "combined_z": combined_z,
    }
    if yes_price is not None:
        sig["yes_price"] = yes_price
    return sig


def default_tick_args(coins=None, signals=None, mids=None, spreads=None, hours=None):
    coins = coins or ["BTC"]
    return dict(
        coins=coins,
        signals=signals if signals is not None else {c: make_signal() for c in coins},
        orderbook_mids=mids if mids is not None else {c: 0.5 for c in coins},
        reward_spreads=spreads if spreads is not None else {c: 0.10 for c in coins},
        hours_left=hours if hours is not None else {c: 5.0 for c in coins},
    )


# ---------------------------------------------------------------------------
# 1. Market filtering
# ---------------------------------------------------------------------------

class TestMarketFiltering:
    def test_missing_mid_produces_no_quote_actions(self):
        cfg = QuoteConfig(enabled=True)
        qm = QuoteManager(cfg, make_bridge())
        result = qm.tick(**default_tick_args(mids={}))
        assert len(result.actions) == 0

    def test_skip_low_odds(self):
        cfg = QuoteConfig(enabled=True)
        qm = QuoteManager(cfg, make_bridge())
        result = qm.tick(**default_tick_args(mids={"BTC": 0.02}))
        assert len(result.actions) == 0

    def test_skip_high_odds(self):
        cfg = QuoteConfig(enabled=True)
        qm = QuoteManager(cfg, make_bridge())
        result = qm.tick(**default_tick_args(mids={"BTC": 0.98}))
        assert len(result.actions) == 0

    def test_skip_low_hours(self):
        cfg = QuoteConfig(enabled=True, min_hours_for_quoting=1.0)
        qm = QuoteManager(cfg, make_bridge())
        result = qm.tick(**default_tick_args(hours={"BTC": 0.5}))
        assert len(result.actions) == 0

    def test_skip_capital_per_market(self):
        cfg = QuoteConfig(enabled=True, max_capital_per_market=10.0)
        qm = QuoteManager(cfg, make_bridge())
        qm._capital_used["BTC"] = 10.0
        result = qm.tick(**default_tick_args())
        assert len(result.actions) == 0

    def test_skip_total_capital(self):
        cfg = QuoteConfig(enabled=True, max_total_capital=5.0)
        qm = QuoteManager(cfg, make_bridge())
        qm._capital_used["BTC"] = 5.0
        result = qm.tick(**default_tick_args())
        assert len(result.actions) == 0


# ---------------------------------------------------------------------------
# 2. Symmetric quoting (low z)
# ---------------------------------------------------------------------------

class TestSymmetric:
    def test_symmetric_both_sides(self):
        cfg = QuoteConfig(enabled=True, base_size=100)
        qm = QuoteManager(cfg, make_bridge())
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.5, z_score=0.0)},
        ))
        assert qm.state("BTC") == QuoteState.SYMMETRIC
        sides = {a.side for a in result.actions}
        assert sides == {"YES", "NO"}
        for a in result.actions:
            assert a.action == "place"

    def test_symmetric_distances_equal(self):
        cfg = QuoteConfig(enabled=True, inner_fraction=0.2, outer_fraction=0.9)
        qm = QuoteManager(cfg, make_bridge())
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.5, z_score=0.0)},
            mids={"BTC": 0.5}, spreads={"BTC": 0.10},
        ))
        yes_a = [a for a in result.actions if a.side == "YES"][0]
        no_a = [a for a in result.actions if a.side == "NO"][0]
        # z=0 → base_dist = inner = 0.02
        # no skew → symmetric
        assert abs(yes_a.price - (0.5 - 0.02)) < 1e-9
        assert abs(no_a.price - (0.5 + 0.02)) < 1e-9


# ---------------------------------------------------------------------------
# 3. Skewed quoting
# ---------------------------------------------------------------------------

class TestSkewed:
    def test_skewed_state(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        # z=1.0 → ratio=0.667 > 0.5 → SKEWED
        qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.6, z_score=1.0)},
        ))
        assert qm.state("BTC") == QuoteState.SKEWED

    def test_skew_tightens_favored(self):
        cfg = QuoteConfig(enabled=True, inner_fraction=0.2, outer_fraction=0.9, skew_sensitivity=0.5)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        # Positive combined_z should tighten YES relative to NO.
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.6, z_score=1.0, combined_z=0.35)},
            mids={"BTC": 0.5}, spreads={"BTC": 0.10},
        ))
        yes_a = [a for a in result.actions if a.side == "YES"][0]
        no_a = [a for a in result.actions if a.side == "NO"][0]
        # YES should be tighter (closer to mid) than NO
        yes_dist = 0.5 - yes_a.price
        no_dist = no_a.price - 0.5
        assert yes_dist < no_dist

    def test_skew_direction_follows_combined_z_sign(self):
        cfg = QuoteConfig(enabled=True, inner_fraction=0.2, outer_fraction=0.9, skew_sensitivity=0.5)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(z_score=1.0, combined_z=-0.35)},
            mids={"BTC": 0.5}, spreads={"BTC": 0.10},
        ))
        yes_a = [a for a in result.actions if a.side == "YES"][0]
        no_a = [a for a in result.actions if a.side == "NO"][0]
        yes_dist = 0.5 - yes_a.price
        no_dist = no_a.price - 0.5
        assert yes_dist > no_dist


# ---------------------------------------------------------------------------
# 4. One-sided mode
# ---------------------------------------------------------------------------

class TestOneSided:
    def test_one_sided_state(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "btc_z_threshold": 0.5, "combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        # z=1.5 → ratio=1.0 → ONE_SIDED
        qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.6, z_score=1.5)},
        ))
        assert qm.state("BTC") == QuoteState.ONE_SIDED

    def test_one_sided_cancels_opposing(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        # Set up existing NO order
        qm.set_orders("BTC", {"NO": {"price": 0.55, "size": 100, "order_id": "no_1"}})
        # combined_z > 0 → favors YES, opposing = NO
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.6, z_score=1.5, combined_z=1.0)},
        ))
        cancel_actions = [a for a in result.actions if a.action == "cancel"]
        assert len(cancel_actions) == 1
        assert cancel_actions[0].side == "NO"

    def test_one_sided_favored_at_inner(self):
        cfg = QuoteConfig(enabled=True, inner_fraction=0.2)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(model_prob=0.6, z_score=1.5, combined_z=1.0)},
            mids={"BTC": 0.5}, spreads={"BTC": 0.10},
        ))
        place_actions = [a for a in result.actions if a.action == "place"]
        assert len(place_actions) == 1
        assert place_actions[0].side == "YES"
        # inner = 0.2 * 0.10 = 0.02; YES price = 0.5 - 0.02 = 0.48
        assert abs(place_actions[0].price - 0.48) < 1e-9

    def test_one_sided_favored_side_uses_combined_z_sign(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"combined_z_threshold": 0.7})
        qm = QuoteManager(cfg, bridge)
        result = qm.tick(**default_tick_args(
            signals={"BTC": make_signal(combined_z=-1.0)},
            mids={"BTC": 0.5}, spreads={"BTC": 0.10},
        ))
        place_actions = [a for a in result.actions if a.action == "place"]
        assert len(place_actions) == 1
        assert place_actions[0].side == "NO"


# ---------------------------------------------------------------------------
# 5. Z-ratio clamping
# ---------------------------------------------------------------------------

class TestZClamping:
    def test_z_clamped_above_1(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.0})
        qm = QuoteManager(cfg, bridge)
        # z=5.0 → ratio=5.0 clamped to 1.0 → ONE_SIDED
        qm.tick(**default_tick_args(
            signals={"BTC": make_signal(z_score=5.0)},
        ))
        assert qm.state("BTC") == QuoteState.ONE_SIDED

    def test_z_clamped_below_0(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5})
        qm = QuoteManager(cfg, bridge)
        # z=0 → ratio=0 → SYMMETRIC
        qm.tick(**default_tick_args(
            signals={"BTC": make_signal(z_score=0.0)},
        ))
        assert qm.state("BTC") == QuoteState.SYMMETRIC

    def test_spot_z_threshold_triggers_one_sided_without_btc(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 1.5, "btc_z_threshold": 10.0, "combined_z_threshold": 10.0})
        qm = QuoteManager(cfg, bridge)
        qm.tick(**default_tick_args(
            signals={"BTC": make_signal(z_score=1.5, btc_z_score=0.0, combined_z=0.0)},
        ))
        assert qm.state("BTC") == QuoteState.ONE_SIDED

    def test_btc_z_threshold_triggers_one_sided_without_spot(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(global_params={"edge_z_threshold": 10.0, "btc_z_threshold": 0.5, "combined_z_threshold": 10.0})
        qm = QuoteManager(cfg, bridge)
        qm.tick(**default_tick_args(
            signals={"BTC": make_signal(z_score=0.0, btc_z_score=0.5, combined_z=0.0)},
        ))
        assert qm.state("BTC") == QuoteState.ONE_SIDED


# ---------------------------------------------------------------------------
# 6. Fill handling
# ---------------------------------------------------------------------------

class TestFillHandling:
    def test_fill_transitions_to_filled(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        qm.on_fill("BTC", "YES", 0.45, 100)
        assert qm.state("BTC") == QuoteState.FILLED

    def test_fill_emits_close_order(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        result = qm.on_fill("BTC", "YES", 0.45, 100)
        close_actions = [a for a in result.actions if a.action == "close_order"]
        assert len(close_actions) == 1
        assert close_actions[0].side == "YES"
        assert abs(close_actions[0].price - 0.50) < 1e-9  # 0.45 + 0.05

    def test_fill_no_side_emits_close_for_no(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        result = qm.on_fill("BTC", "NO", 0.55, 100)
        close_actions = [a for a in result.actions if a.action == "close_order"]
        assert len(close_actions) == 1
        assert abs(close_actions[0].price - 0.50) < 1e-9  # 0.55 - 0.05

    def test_filled_state_skips_quoting(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        qm.on_fill("BTC", "YES", 0.45, 100)
        result = qm.tick(**default_tick_args())
        # Should not emit place/update actions
        place_update = [a for a in result.actions if a.action in ("place", "update")]
        assert len(place_update) == 0


# ---------------------------------------------------------------------------
# 7. Close fill → back to quoting
# ---------------------------------------------------------------------------

class TestCloseFill:
    def test_close_fill_resets_to_idle(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        qm.on_fill("BTC", "YES", 0.45, 100)
        qm.on_close_fill("BTC")
        assert qm.state("BTC") == QuoteState.IDLE

    def test_close_fill_resumes_quoting(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        qm.on_fill("BTC", "YES", 0.45, 100)
        qm.on_close_fill("BTC")
        result = qm.tick(**default_tick_args())
        assert len(result.actions) > 0


# ---------------------------------------------------------------------------
# 8. Both sides filled → CONVERGED
# ---------------------------------------------------------------------------

class TestConverged:
    def test_both_fills_converged(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        qm.on_fill("BTC", "YES", 0.45, 100)
        qm.on_fill("BTC", "NO", 0.55, 100)
        assert qm.state("BTC") == QuoteState.CONVERGED

    def test_converged_skips_quoting(self):
        cfg = QuoteConfig(enabled=True)
        bridge = make_bridge(coin_params={"BTC": {"tp_distance": 0.05}})
        qm = QuoteManager(cfg, bridge)
        qm.on_fill("BTC", "YES", 0.45, 100)
        qm.on_fill("BTC", "NO", 0.55, 100)
        result = qm.tick(**default_tick_args())
        place_update = [a for a in result.actions if a.action in ("place", "update")]
        assert len(place_update) == 0


# ---------------------------------------------------------------------------
# 9. Reprice threshold
# ---------------------------------------------------------------------------

class TestRepriceThreshold:
    def test_no_update_if_within_threshold(self):
        cfg = QuoteConfig(enabled=True, reprice_threshold=0.01)
        qm = QuoteManager(cfg, make_bridge())
        # First tick places orders
        result1 = qm.tick(**default_tick_args(mids={"BTC": 0.5}, spreads={"BTC": 0.10}))
        assert len(result1.actions) == 2
        # Assign order IDs
        for a in result1.actions:
            qm._current_orders["BTC"][a.side]["order_id"] = f"ord_{a.side}"

        # Tick with barely changed mid
        result2 = qm.tick(**default_tick_args(mids={"BTC": 0.5005}, spreads={"BTC": 0.10}))
        update_actions = [a for a in result2.actions if a.action == "update"]
        assert len(update_actions) == 0

    def test_update_if_exceeds_threshold(self):
        cfg = QuoteConfig(enabled=True, reprice_threshold=0.01)
        qm = QuoteManager(cfg, make_bridge())
        result1 = qm.tick(**default_tick_args(mids={"BTC": 0.5}, spreads={"BTC": 0.10}))
        for a in result1.actions:
            qm._current_orders["BTC"][a.side]["order_id"] = f"ord_{a.side}"

        # Significant price change
        result2 = qm.tick(**default_tick_args(mids={"BTC": 0.55}, spreads={"BTC": 0.10}))
        update_actions = [a for a in result2.actions if a.action == "update"]
        assert len(update_actions) > 0


# ---------------------------------------------------------------------------
# 10. Capital limit enforcement
# ---------------------------------------------------------------------------

class TestCapitalLimits:
    def test_size_capped_by_available_capital(self):
        cfg = QuoteConfig(enabled=True, base_size=100, max_capital_per_market=30.0)
        qm = QuoteManager(cfg, make_bridge())
        qm._capital_used["BTC"] = 20.0
        result = qm.tick(**default_tick_args())
        for a in result.actions:
            if a.action == "place":
                assert a.size <= 10.0  # 30 - 20 = 10

    def test_total_capital_caps_size(self):
        cfg = QuoteConfig(enabled=True, base_size=100, max_total_capital=25.0)
        qm = QuoteManager(cfg, make_bridge())
        qm._capital_used["BTC"] = 20.0
        result = qm.tick(**default_tick_args())
        for a in result.actions:
            if a.action == "place":
                assert a.size <= 5.0  # 25 - 20 = 5


# ---------------------------------------------------------------------------
# 11. set_order_id prevents duplicate place actions
# ---------------------------------------------------------------------------

class TestSetOrderId:
    def test_set_order_id_prevents_duplicate_place(self):
        """After set_order_id, tick should emit update (not place) for that side."""
        cfg = QuoteConfig(enabled=True, reprice_threshold=0.0001)
        qm = QuoteManager(cfg, make_bridge())
        # First tick: places both sides
        result1 = qm.tick(**default_tick_args(mids={"BTC": 0.5}, spreads={"BTC": 0.10}))
        places = [a for a in result1.actions if a.action == "place"]
        assert len(places) == 2

        # Feed back order IDs (simulating controller calling set_order_id)
        for a in places:
            qm.set_order_id("BTC", a.side, f"exec_{a.side}")

        # Second tick with slightly changed mid: should emit updates, not places
        result2 = qm.tick(**default_tick_args(mids={"BTC": 0.52}, spreads={"BTC": 0.10}))
        for a in result2.actions:
            assert a.action != "place", f"Expected no place actions, got {a}"

    def test_set_order_id_on_missing_side_is_noop(self):
        """set_order_id for a side not in _current_orders doesn't crash."""
        cfg = QuoteConfig(enabled=True)
        qm = QuoteManager(cfg, make_bridge())
        # No orders tracked yet — should not raise
        qm.set_order_id("BTC", "YES", "some_id")


# ---------------------------------------------------------------------------
# 12. clear_order allows fresh place
# ---------------------------------------------------------------------------

class TestClearOrder:
    def test_clear_order_allows_fresh_place(self):
        """After clear_order, tick should emit a place action for that side."""
        cfg = QuoteConfig(enabled=True)
        qm = QuoteManager(cfg, make_bridge())
        # First tick places orders
        result1 = qm.tick(**default_tick_args(mids={"BTC": 0.5}, spreads={"BTC": 0.10}))
        for a in result1.actions:
            qm.set_order_id("BTC", a.side, f"exec_{a.side}")

        # Clear the YES side
        qm.clear_order("BTC", "YES")

        # Next tick should place YES again
        result2 = qm.tick(**default_tick_args(mids={"BTC": 0.5}, spreads={"BTC": 0.10}))
        yes_places = [a for a in result2.actions if a.action == "place" and a.side == "YES"]
        assert len(yes_places) == 1

    def test_clear_order_noop_for_unknown(self):
        """clear_order for unknown coin/side doesn't crash."""
        cfg = QuoteConfig(enabled=True)
        qm = QuoteManager(cfg, make_bridge())
        qm.clear_order("UNKNOWN", "YES")  # should not raise
