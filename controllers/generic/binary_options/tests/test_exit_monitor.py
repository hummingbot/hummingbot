"""Tests for ExitMonitor — Phase 1 exit logic."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from controllers.generic.binary_options.exit_monitor import ExitMonitor


def _make_config(settlement_hold_threshold=0.70):
    config = MagicMock()
    config.routing.settlement_hold_threshold = settlement_hold_threshold
    return config


def _make_rb(btc_reversal_multiplier=5.24, close_secs=120.0):
    rb = MagicMock()

    def get_coin_param(coin, key, default=None):
        vals = {"btc_reversal_multiplier": btc_reversal_multiplier, "close_secs": close_secs}
        return vals.get(key, default)
    rb.get_coin_param = get_coin_param
    return rb


class TestRegisterUnregister(unittest.TestCase):
    def test_register_and_unregister(self):
        em = ExitMonitor(_make_config(), _make_rb())
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        assert em._btc_entry_prices["ex1"] == 60000.0
        assert em._executor_directions["ex1"] == "YES"
        assert em._executor_coins["ex1"] == "BTC-5MIN-UP"

        em.unregister("ex1")
        assert "ex1" not in em._btc_entry_prices
        assert "ex1" not in em._executor_directions
        assert "ex1" not in em._executor_coins

    def test_unregister_missing_is_noop(self):
        em = ExitMonitor(_make_config(), _make_rb())
        em.unregister("nonexistent")  # no error


class TestBtcReversal(unittest.TestCase):
    def test_yes_btc_drops_exit(self):
        em = ExitMonitor(_make_config(), _make_rb(btc_reversal_multiplier=5.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        result = em._check_btc_reversal("ex1", 59995.0)  # drop of 5.0
        assert result == {"executor_id": "ex1", "reason": "btc_reversal"}

    def test_no_btc_rises_exit(self):
        em = ExitMonitor(_make_config(), _make_rb(btc_reversal_multiplier=5.0))
        em.register_entry("ex1", "BTC-5MIN-DN", "NO", 60000.0)
        result = em._check_btc_reversal("ex1", 60005.0)  # rise of 5.0
        assert result == {"executor_id": "ex1", "reason": "btc_reversal"}

    def test_below_threshold_no_action(self):
        em = ExitMonitor(_make_config(), _make_rb(btc_reversal_multiplier=5.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        result = em._check_btc_reversal("ex1", 59996.0)  # drop of 4.0
        assert result is None

    def test_favorable_movement_no_action(self):
        """YES position + BTC rising = favorable, no exit."""
        em = ExitMonitor(_make_config(), _make_rb(btc_reversal_multiplier=5.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        result = em._check_btc_reversal("ex1", 60010.0)  # BTC up = good for YES
        assert result is None


class TestSettlement(unittest.TestCase):
    def test_winning_above_threshold_hold(self):
        em = ExitMonitor(_make_config(settlement_hold_threshold=0.70), _make_rb(close_secs=120.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        market = {"end_time": 1000.0, "yes_price": 0.80}
        result = em._check_settlement("ex1", "BTC-5MIN-UP", market, now_ts=900.0)  # 100s to expiry
        assert result is None  # hold

    def test_losing_near_expiry_exit(self):
        em = ExitMonitor(_make_config(settlement_hold_threshold=0.70), _make_rb(close_secs=120.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        market = {"end_time": 1000.0, "yes_price": 0.30}  # losing for YES
        result = em._check_settlement("ex1", "BTC-5MIN-UP", market, now_ts=900.0)
        assert result == {"executor_id": "ex1", "reason": "settlement_exit"}

    def test_not_near_expiry_no_action(self):
        em = ExitMonitor(_make_config(), _make_rb(close_secs=120.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        market = {"end_time": 1000.0, "yes_price": 0.30}
        result = em._check_settlement("ex1", "BTC-5MIN-UP", market, now_ts=500.0)  # 500s away
        assert result is None


class TestCheckAll(unittest.TestCase):
    def test_combined_btc_reversal_priority(self):
        """BTC reversal fires first, settlement check skipped for that executor."""
        em = ExitMonitor(_make_config(), _make_rb(btc_reversal_multiplier=5.0, close_secs=120.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)
        em.register_entry("ex2", "BTC-5MIN-DN", "NO", 60000.0)

        executors = [SimpleNamespace(id="ex1"), SimpleNamespace(id="ex2")]
        market_data = {
            "BTC-5MIN-UP": {"end_time": 1000.0, "yes_price": 0.30},
            "BTC-5MIN-DN": {"end_time": 1000.0, "yes_price": 0.30},
        }
        # BTC dropped 6 → triggers reversal for ex1 (YES), but not ex2 (NO, drop is favorable)
        actions = em.check_all(executors, btc_spot=59994.0, market_data=market_data, now_ts=900.0)

        reasons = {a["executor_id"]: a["reason"] for a in actions}
        assert reasons["ex1"] == "btc_reversal"
        # ex2: NO position, BTC dropped = favorable, no reversal. But near expiry + losing (yes=0.30, NO wants <0.50 → winning)
        # Actually yes_price=0.30 means NO is winning (0.30 < 0.50), prob=0.70 >= 0.70 threshold → hold
        assert "ex2" not in reasons

    def test_check_all_with_dict_executors(self):
        """Executors passed as dicts instead of objects."""
        em = ExitMonitor(_make_config(), _make_rb(btc_reversal_multiplier=5.0, close_secs=120.0))
        em.register_entry("ex1", "BTC-5MIN-UP", "YES", 60000.0)

        executors = [{"id": "ex1"}]
        market_data = {"BTC-5MIN-UP": {"end_time": 1000.0, "yes_price": 0.30}}
        actions = em.check_all(executors, btc_spot=59994.0, market_data=market_data, now_ts=900.0)
        assert len(actions) == 1
        assert actions[0]["reason"] == "btc_reversal"


if __name__ == "__main__":
    unittest.main()
