"""Tests for BinaryOptionsController."""
import asyncio
import json
import sys
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from controllers.generic.binary_options.config import BinaryOptionsControllerConfig

# conftest.py stubs hummingbot modules; import after it runs
from controllers.generic.binary_options.controller import BinaryOptionsController

# Re-import stub classes for isinstance checks
_sma = sys.modules["hummingbot.strategy_v2.models.executor_actions"]
_CreateExecutorAction = _sma.CreateExecutorAction
_StopExecutorAction = _sma.StopExecutorAction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_runtime(tmp_path):
    runtime = {
        "trading_enabled": True, "paused": False,
        "stop_loss_pct": 0.03, "take_profit_pct": 0.10,
        "trailing_trigger_pct": 0.05, "trailing_distance_pct": 0.02,
        "base_timeout_secs": 3600,
        "coins": {"BTC": {"tier": "MAIN"}},
    }
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(runtime))
    return str(path)


@pytest.fixture
def tmp_config(tmp_path):
    cfg = {
        "poll_interval_ms": 1500, "min_btc_delta": 0.5,
        "min_coin_delta": 0.001, "dyn_thresh_min_samples": 5,
        "dyn_thresh_floor_pct": 0.5,
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    return str(path)


@pytest.fixture
def config(tmp_runtime, tmp_config):
    return BinaryOptionsControllerConfig(
        id="test_bo", runtime_json_path=tmp_runtime, config_json_path=tmp_config,
    )


@pytest.fixture
def controller(config):
    ctrl = BinaryOptionsController(config, MagicMock(), asyncio.Queue())
    ctrl.connectors = {config.connector_name: MagicMock()}
    return ctrl


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInstantiation:
    def test_modules_wired(self, controller):
        for attr in ("runtime_bridge", "roster", "spot_feed", "signal_engine",
                      "market_manager", "position_tracker", "exit_monitor", "action_router"):
            assert getattr(controller, attr) is not None

    def test_connector_none_before_start(self, controller):
        assert controller.market_manager._connector is None

    def test_on_start_wires_connector(self, controller):
        controller.on_start()
        assert controller.market_manager._connector is not None


class TestUpdateProcessedData:
    def test_calls_modules_in_order(self, controller):
        controller.spot_feed = MagicMock()
        controller.spot_feed.get_prices.return_value = {"BTC": 100000.0}
        controller.market_manager = MagicMock()
        controller.market_manager.build_market_data.return_value = {
            "BTC": {"yes_price": 0.6, "pyth_address": "0xabc"},
        }
        controller.signal_engine = MagicMock()
        controller.signal_engine.tick.return_value = {"BTC": {"direction": "YES", "edge": 0.05}}
        controller.runtime_bridge = MagicMock()

        asyncio.get_event_loop().run_until_complete(controller.update_processed_data())

        controller.runtime_bridge.check.assert_called_once()
        controller.spot_feed.get_prices.assert_called_once()
        controller.market_manager.discover.assert_called_once()
        controller.market_manager.evaluate.assert_called_once()
        controller.market_manager.build_market_data.assert_called_once()
        controller.spot_feed.update_addresses.assert_called_once_with({"BTC": "0xabc"})
        controller.signal_engine.tick.assert_called_once()
        assert controller.processed_data["btc_spot"] == 100000.0


class TestDetermineExecutorActions:
    def _wire_mocks(self, controller, trading=True, exits=None, entries=None, closed=None):
        controller.runtime_bridge = MagicMock()
        controller.runtime_bridge.should_trade.return_value = trading
        controller.runtime_bridge.get_coin_param = MagicMock(side_effect=lambda c, k, d=None: {
            "stop_loss_pct": 0.03, "take_profit_pct": 0.10,
            "trailing_trigger_pct": 0.05, "trailing_distance_pct": 0.02,
            "base_timeout_secs": 3600,
        }.get(k, d))
        controller.processed_data = {
            "now_ts": 1000.0, "market_data": {}, "btc_spot": 100000.0, "coins": {},
        }
        controller.market_manager = MagicMock()
        controller.market_manager.check_expiry.return_value = set()
        controller.exit_monitor = MagicMock()
        controller.exit_monitor.check_all.return_value = exits or []
        controller.exit_monitor._executor_coins = {e.id: "BTC" for e in (closed or []) if hasattr(e, "id")}
        controller.action_router = MagicMock()
        controller.action_router.route.return_value = entries or []
        controller.position_tracker = MagicMock()
        controller.executors_info = closed or []

    def test_empty_when_trading_disabled(self, controller):
        self._wire_mocks(controller, trading=False)
        assert controller.determine_executor_actions() == []

    def test_stop_actions_for_exits(self, controller):
        self._wire_mocks(controller, exits=[{"executor_id": "ex1", "reason": "btc_reversal"}])
        actions = controller.determine_executor_actions()
        assert len(actions) == 1
        assert isinstance(actions[0], _StopExecutorAction)
        assert actions[0].executor_id == "ex1"

    def test_create_actions_for_entries(self, controller):
        self._wire_mocks(controller, entries=[{
            "coin": "BTC", "slug": "BTC-YES-100K", "entry_price": 0.55,
            "size": 10.0, "direction": "YES",
        }])
        actions = controller.determine_executor_actions()
        assert len(actions) == 1
        assert isinstance(actions[0], _CreateExecutorAction)
        assert actions[0].executor_config.trading_pair == "BTC-YES-100K"
        controller.exit_monitor.register_entry.assert_called_once()
        controller.position_tracker.record_open.assert_called_once()

    def test_closed_executor_sync(self, controller):
        ei = MagicMock()
        ei.is_closed = True
        ei.id = "closed1"
        ei.net_pnl_quote = Decimal("5.0")
        self._wire_mocks(controller, closed=[ei])
        controller.exit_monitor._executor_coins = {"closed1": "BTC"}
        controller.determine_executor_actions()
        controller.position_tracker.record_close.assert_called_once_with("BTC", "closed1", 5.0)
        controller.exit_monitor.unregister.assert_called_once_with("closed1")


class TestToFormatStatus:
    def test_basic_output(self, controller):
        controller.runtime_bridge = MagicMock()
        controller.runtime_bridge.should_trade.return_value = True
        controller.position_tracker = MagicMock()
        controller.position_tracker.open_count = 2
        controller.position_tracker.total_exposure = 150.0
        controller.processed_data = {
            "btc_spot": 100000.0,
            "coins": {"BTC": {"direction": "YES", "edge": 0.08}},
        }
        text = "\n".join(controller.to_format_status())
        assert "ON" in text
        assert "BTC" in text
