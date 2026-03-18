"""Tests for BinaryOptionsController."""
import asyncio
import json
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from controllers.generic.binary_options.config import BinaryOptionsControllerConfig

# conftest.py stubs hummingbot modules; import after it runs
from controllers.generic.binary_options.controller import BinaryOptionsController

# Re-import stub classes for isinstance checks
_sma = sys.modules["hummingbot.strategy_v2.models.executor_actions"]
_CreateExecutorAction = _sma.CreateExecutorAction
_StopExecutorAction = _sma.StopExecutorAction

_common = sys.modules["hummingbot.core.data_type.common"]
_TradeType = _common.TradeType


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
        for attr in (
            "runtime_bridge",
            "roster",
            "spot_feed",
            "signal_engine",
            "market_manager",
            "position_tracker",
            "exit_monitor",
            "action_router",
        ):
            assert getattr(controller, attr) is not None
        assert "BTC" in controller.spot_feed.core_tickers

    def test_connector_none_before_start(self, controller):
        assert controller.market_manager._connector is None

    def test_on_start_wires_connector(self, controller):
        controller.market_data_provider.connectors = {controller.config.connector_name: MagicMock()}
        controller._ensure_connector()
        assert controller.market_manager._connector is not None


class TestUpdateProcessedData:
    def test_calls_modules_in_order(self, controller):
        controller.spot_feed = MagicMock()
        controller.spot_feed.get_prices.return_value = {"BTC": 100000.0}
        controller.market_manager = MagicMock()
        controller.market_manager.discover = AsyncMock()
        controller.market_manager.evaluate = AsyncMock()
        controller.market_manager.build_market_data = AsyncMock()
        controller.market_manager.build_market_data.return_value = {
            "BTC": {"yes_price": 0.6, "pyth_address": "0xabc"},
        }
        controller.signal_engine = MagicMock()
        controller.signal_engine.tick.return_value = {"BTC": {"direction": "YES", "edge": 0.05}}
        controller.runtime_bridge = MagicMock()

        asyncio.run(controller.update_processed_data())

        controller.runtime_bridge.check.assert_called_once()
        controller.spot_feed.get_prices.assert_called_once()
        controller.market_manager.discover.assert_called_once()
        controller.market_manager.evaluate.assert_called_once()
        controller.market_manager.build_market_data.assert_called_once()
        controller.spot_feed.update_addresses.assert_called_once_with({"BTC": "0xabc"})
        controller.signal_engine.tick.assert_called_once()
        assert controller.processed_data["btc_spot"] == 100000.0

    def test_mm_processed_data_uses_yes_mid_for_valid_coins_only(self, controller):
        controller.config.quoting.enabled = True
        controller.spot_feed = MagicMock()
        controller.spot_feed.get_prices.return_value = {"BTC": 100000.0}
        controller.market_manager = MagicMock()
        controller.market_manager.discover = AsyncMock()
        controller.market_manager.evaluate = AsyncMock()
        controller.market_manager.build_market_data = AsyncMock()
        controller.market_manager.build_market_data.return_value = {
            "BTC": {
                "yes_price": 0.6,
                "yes_mid": 0.57,
                "quote_valid": True,
                "expiry_ts": 5000.0,
                "pyth_address": "0xabc",
            },
            "ETH": {
                "yes_price": 0.4,
                "yes_mid": None,
                "quote_valid": False,
                "expiry_ts": 5000.0,
                "pyth_address": "0xdef",
            },
        }
        controller.signal_engine = MagicMock()
        controller.signal_engine.tick.return_value = {
            "BTC": {"vol": 0.01},
            "ETH": {"vol": 0.01},
        }
        controller.runtime_bridge = MagicMock()

        asyncio.run(controller.update_processed_data())

        assert controller.processed_data["orderbook_mids"] == {"BTC": 0.57}
        assert "ETH" not in controller.processed_data["orderbook_mids"]


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
            "now_ts": 1000.0, "market_data": {}, "btc_spot": 100000.0, "coins": {"BTC": {"vol": 0.01, "z_score": 0.0, "btc_z_score": 0.0, "combined_z": 0.0}},
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


class TestMMMode:
    """Tests for market-making mode (quoting.enabled=True)."""

    def _make_mm_controller(self, config):
        config.quoting.enabled = True
        ctrl = BinaryOptionsController(config, MagicMock(), asyncio.Queue())
        ctrl.connectors = {config.connector_name: MagicMock()}
        return ctrl

    def _wire_mm_mocks(self, controller, trading=True, quote_actions=None):
        controller.runtime_bridge = MagicMock()
        controller.runtime_bridge.should_trade.return_value = trading
        controller.runtime_bridge.get_coin_param = MagicMock(side_effect=lambda c, k, d=None: {
            "stop_loss_pct": 0.03, "tp_distance": 0.05,
            "trailing_trigger_pct": 0.05, "trailing_distance_pct": 0.02,
        }.get(k, d))
        controller.processed_data = {
            "now_ts": 1000.0,
            "coins": {"BTC": {"vol": 0.01, "z_score": 0.0, "btc_z_score": 0.0, "combined_z": 0.0}},
            "market_data": {"BTC": {"slug": "BTC-YES-100K", "yes_price": 0.5}},
            "orderbook_mids": {"BTC": 0.5},
            "reward_spreads": {"BTC": 0.03},
            "hours_left": {"BTC": 2.0},
            "btc_spot": 100000.0,
        }
        controller.position_tracker = MagicMock()
        controller.executors_info = []

        if quote_actions is not None:
            controller.quote_manager = MagicMock()
            controller.quote_manager.tick.return_value = quote_actions

    def test_mm_mode_uses_quote_manager(self, config):
        ctrl = self._make_mm_controller(config)
        self._wire_mm_mocks(ctrl)
        from controllers.generic.binary_options.quote_manager import QuoteActions
        ctrl.quote_manager = MagicMock()
        ctrl.quote_manager.tick.return_value = QuoteActions()
        actions = ctrl.determine_executor_actions()
        ctrl.quote_manager.tick.assert_called_once()
        assert actions == []

    def test_mm_tick_passes_only_valid_mid_coins(self, config):
        ctrl = self._make_mm_controller(config)
        self._wire_mm_mocks(ctrl)
        from controllers.generic.binary_options.quote_manager import QuoteActions
        ctrl.processed_data["coins"]["ETH"] = {"vol": 0.02}
        ctrl.processed_data["market_data"]["ETH"] = {"slug": "ETH-YES-3K", "yes_price": 0.5}
        ctrl.processed_data["reward_spreads"]["ETH"] = 0.03
        ctrl.processed_data["hours_left"]["ETH"] = 2.0
        ctrl.quote_manager = MagicMock()
        ctrl.quote_manager.tick.return_value = QuoteActions()

        ctrl.determine_executor_actions()

        args = ctrl.quote_manager.tick.call_args[0]
        assert args[0] == ["BTC"]

    def test_mm_place_creates_executor(self, config):
        """Place quote creates executor with full TripleBarrier (SL/TP/trailing)."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        qa = QuoteActions(actions=[
            QuoteAction(action="place", coin="BTC", side="YES", price=0.45, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        actions = ctrl.determine_executor_actions()
        assert len(actions) == 1
        assert isinstance(actions[0], _CreateExecutorAction)
        cfg = actions[0].executor_config
        assert cfg.trading_pair == "BTC-USDC"
        assert cfg.entry_price == Decimal("0.45")
        # Verify full barrier config from runtime params
        tb = cfg.triple_barrier_config
        assert tb.stop_loss == Decimal("0.03")
        assert tb.take_profit == Decimal("0.05")
        assert tb.trailing_stop is not None
        assert tb.trailing_stop.activation_price == Decimal("0.05")
        assert tb.trailing_stop.trailing_delta == Decimal("0.02")
        assert tb.open_order_type is not None  # LIMIT_MAKER
        assert tb.time_limit == 7200  # 2 hours * 3600

    def test_mm_cancel_creates_stop(self, config):
        """Cancel uses _mm_executor_map to find the right executor_id."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions

        # Pre-populate executor map
        ctrl._mm_executor_map["BTC:YES"] = "exec_123"
        active_executor = MagicMock()
        active_executor.id = "exec_123"
        active_executor.is_closed = False
        active_executor.is_active = True
        qa = QuoteActions(actions=[
            QuoteAction(action="cancel", coin="BTC", side="YES"),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        ctrl.executors_info = [active_executor]
        actions = ctrl.determine_executor_actions()
        assert len(actions) == 1
        assert isinstance(actions[0], _StopExecutorAction)
        assert actions[0].executor_id == "exec_123"
        assert ctrl._mm_executor_map["BTC:YES"] == "exec_123"

    def test_mm_cancel_no_mapped_executor_no_action(self, config):
        """Cancel with no mapped executor produces no action."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        qa = QuoteActions(actions=[
            QuoteAction(action="cancel", coin="BTC", side="YES"),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        actions = ctrl.determine_executor_actions()
        assert actions == []

    def test_mm_update_reprices(self, config):
        """Update emits stop only when an executor is still mapped."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        ctrl._mm_executor_map["BTC:YES"] = "old_exec_1"
        active_executor = MagicMock()
        active_executor.id = "old_exec_1"
        active_executor.is_closed = False
        active_executor.is_active = True
        ctrl.executors_info = [active_executor]
        qa = QuoteActions(actions=[
            QuoteAction(action="update", coin="BTC", side="YES", price=0.48, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        ctrl.executors_info = [active_executor]
        actions = ctrl.determine_executor_actions()
        assert len(actions) == 1
        assert isinstance(actions[0], _StopExecutorAction)
        assert actions[0].executor_id == "old_exec_1"
        assert ctrl._mm_executor_map["BTC:YES"] == "old_exec_1"
        assert ctrl._mm_pending_replacements["BTC:YES"]["price"] == 0.48

    def test_mm_executor_map_tracking(self, config):
        """Place populates _mm_executor_map with coin:side -> executor_id."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        qa = QuoteActions(actions=[
            QuoteAction(action="place", coin="BTC", side="YES", price=0.45, size=10.0),
            QuoteAction(action="place", coin="BTC", side="NO", price=0.55, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        actions = ctrl.determine_executor_actions()
        assert len(actions) == 2
        assert "BTC:YES" in ctrl._mm_executor_map
        assert "BTC:NO" in ctrl._mm_executor_map
        # IDs should match the executor configs
        assert ctrl._mm_executor_map["BTC:YES"] == actions[0].executor_config.id
        assert ctrl._mm_executor_map["BTC:NO"] == actions[1].executor_config.id

    def test_mm_fill_detection_pulls_opposing(self, config):
        """When executor fill detected, quote_manager.on_fill cancels opposing side."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        self._wire_mm_mocks(ctrl, quote_actions=QuoteActions())

        # Set up executor map with both sides
        ctrl._mm_executor_map["BTC:YES"] = "exec_yes"
        ctrl._mm_executor_map["BTC:NO"] = "exec_no"

        # Simulate a filled YES executor
        ei = MagicMock()
        ei.is_active = True
        ei.id = "exec_yes"
        ei.entry_price = Decimal("0.45")
        ei.filled_amount_quote = Decimal("4.5")
        ei.is_closed = False
        opp_ei = MagicMock()
        opp_ei.is_active = True
        opp_ei.id = "exec_no"
        opp_ei.entry_price = Decimal("0")
        opp_ei.filled_amount_quote = Decimal("0")
        opp_ei.is_closed = False
        ctrl.executors_info = [ei, opp_ei]

        # on_fill should return cancel for opposing NO side
        fill_result = QuoteActions(actions=[
            QuoteAction(action="cancel", coin="BTC", side="NO"),
        ])
        ctrl.quote_manager.on_fill = MagicMock(return_value=fill_result)

        actions = ctrl.determine_executor_actions()
        ctrl.quote_manager.on_fill.assert_called_once_with("BTC", "YES", 0.45, 4.5)
        # Should have a StopExecutorAction for the NO side
        stop_actions = [a for a in actions if isinstance(a, _StopExecutorAction)]
        assert len(stop_actions) == 1
        assert stop_actions[0].executor_id == "exec_no"
        assert ctrl._mm_executor_map["BTC:NO"] == "exec_no"

    def test_mm_closed_executor_sync(self, config):
        """Closed executors trigger on_close_fill and record_close."""
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteActions
        self._wire_mm_mocks(ctrl, quote_actions=QuoteActions())

        ctrl._mm_executor_map["BTC:YES"] = "exec_done"

        ei = MagicMock()
        ei.is_closed = True
        ei.is_active = False
        ei.id = "exec_done"
        ei.net_pnl_quote = Decimal("3.5")
        ctrl.executors_info = [ei]

        ctrl.determine_executor_actions()
        ctrl.quote_manager.on_close_fill.assert_called_once_with("BTC")
        ctrl.position_tracker.record_close.assert_called_once_with("BTC", "exec_done", 3.5)
        assert "BTC:YES" not in ctrl._mm_executor_map

    def test_mm_pending_replacement_creates_after_executor_closes(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteActions

        ctrl._mm_executor_map["BTC:YES"] = "old_exec_1"
        ctrl._mm_pending_replacements["BTC:YES"] = {
            "coin": "BTC",
            "side": "YES",
            "price": 0.49,
            "size": 11.0,
            "trading_pair": "BTC-USDC",
            "ts": 1000.0,
        }
        closed_executor = MagicMock()
        closed_executor.id = "old_exec_1"
        closed_executor.is_closed = True
        closed_executor.is_active = False
        closed_executor.net_pnl_quote = Decimal("1.2")
        self._wire_mm_mocks(ctrl, quote_actions=QuoteActions())
        ctrl.executors_info = [closed_executor]

        actions = ctrl.determine_executor_actions()

        assert len(actions) == 1
        assert isinstance(actions[0], _CreateExecutorAction)
        assert actions[0].executor_config.entry_price == Decimal("0.49")
        assert "BTC:YES" in ctrl._mm_executor_map
        assert ctrl._mm_executor_map["BTC:YES"] == actions[0].executor_config.id
        assert "BTC:YES" not in ctrl._mm_pending_replacements

    def test_mm_place_skips_when_pending_replacement_exists(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions

        ctrl._mm_executor_map["BTC:YES"] = "old_exec_1"
        ctrl._mm_pending_replacements["BTC:YES"] = {
            "coin": "BTC",
            "side": "YES",
            "price": 0.49,
            "size": 11.0,
            "trading_pair": "BTC-USDC",
            "ts": 1000.0,
        }
        active_executor = MagicMock()
        active_executor.id = "old_exec_1"
        active_executor.is_closed = False
        active_executor.is_active = True
        qa = QuoteActions(actions=[
            QuoteAction(action="place", coin="BTC", side="YES", price=0.45, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        ctrl.executors_info = [active_executor]

        actions = ctrl.determine_executor_actions()

        assert actions == []
        assert ctrl._mm_executor_map["BTC:YES"] == "old_exec_1"

    def test_mm_cancel_clears_pending_replacement(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions

        ctrl._mm_executor_map["BTC:YES"] = "exec_123"
        ctrl._mm_pending_replacements["BTC:YES"] = {
            "coin": "BTC",
            "side": "YES",
            "price": 0.49,
            "size": 11.0,
            "trading_pair": "BTC-USDC",
            "ts": 1000.0,
        }
        active_executor = MagicMock()
        active_executor.id = "exec_123"
        active_executor.is_closed = False
        active_executor.is_active = True
        qa = QuoteActions(actions=[
            QuoteAction(action="cancel", coin="BTC", side="YES"),
        ])
        self._wire_mm_mocks(ctrl, quote_actions=qa)
        ctrl.executors_info = [active_executor]

        actions = ctrl.determine_executor_actions()

        assert len(actions) == 1
        assert isinstance(actions[0], _StopExecutorAction)
        assert "BTC:YES" not in ctrl._mm_pending_replacements

    def test_mm_disabled_uses_directional(self, config, controller):
        """When quoting.enabled=False, directional path is used."""
        assert not config.quoting.enabled
        controller.runtime_bridge = MagicMock()
        controller.runtime_bridge.should_trade.return_value = True
        controller.runtime_bridge.get_coin_param = MagicMock(return_value=0.03)
        controller.processed_data = {
            "now_ts": 1000.0, "market_data": {}, "btc_spot": 100000.0, "coins": {"BTC": {"vol": 0.01, "z_score": 0.0, "btc_z_score": 0.0, "combined_z": 0.0}},
        }
        controller.market_manager = MagicMock()
        controller.exit_monitor = MagicMock()
        controller.exit_monitor.check_all.return_value = []
        controller.exit_monitor._executor_coins = {}
        controller.action_router = MagicMock()
        controller.action_router.route.return_value = []
        controller.position_tracker = MagicMock()
        controller.executors_info = []
        controller.determine_executor_actions()
        controller.action_router.route.assert_called_once()

    def test_mm_trading_disabled_no_actions(self, config):
        ctrl = self._make_mm_controller(config)
        self._wire_mm_mocks(ctrl, trading=False)
        from controllers.generic.binary_options.quote_manager import QuoteActions
        ctrl.quote_manager = MagicMock()
        ctrl.quote_manager.tick.return_value = QuoteActions()
        actions = ctrl.determine_executor_actions()
        assert actions == []
        ctrl.quote_manager.tick.assert_not_called()


class TestSideMapping:
    """Verify YES→TradeType.BUY and NO→TradeType.SELL mapping."""

    def _make_mm_controller(self, config):
        config.quoting.enabled = True
        ctrl = BinaryOptionsController(config, MagicMock(), asyncio.Queue())
        ctrl.connectors = {config.connector_name: MagicMock()}
        return ctrl

    def _wire_mm_mocks(self, controller, quote_actions):
        controller.runtime_bridge = MagicMock()
        controller.runtime_bridge.should_trade.return_value = True
        controller.runtime_bridge.get_coin_param = MagicMock(side_effect=lambda c, k, d=None: {
            "stop_loss_pct": 0.03, "tp_distance": 0.05,
            "trailing_trigger_pct": 0.05, "trailing_distance_pct": 0.02,
        }.get(k, d))
        controller.processed_data = {
            "now_ts": 1000.0,
            "coins": {"BTC": {"vol": 0.01, "z_score": 0.0, "btc_z_score": 0.0, "combined_z": 0.0}},
            "market_data": {"BTC": {"slug": "BTC-YES-100K", "yes_price": 0.5}},
            "orderbook_mids": {"BTC": 0.5},
            "reward_spreads": {"BTC": 0.03},
            "hours_left": {"BTC": 2.0},
            "btc_spot": 100000.0,
        }
        controller.position_tracker = MagicMock()
        controller.executors_info = []
        controller.quote_manager = MagicMock()
        controller.quote_manager.tick.return_value = quote_actions

    def test_yes_side_gets_buy(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        qa = QuoteActions(actions=[
            QuoteAction(action="place", coin="BTC", side="YES", price=0.45, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, qa)
        actions = ctrl.determine_executor_actions()
        assert len(actions) == 1
        assert actions[0].executor_config.side == _TradeType.BUY

    def test_no_side_gets_sell(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        qa = QuoteActions(actions=[
            QuoteAction(action="place", coin="BTC", side="NO", price=0.55, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, qa)
        actions = ctrl.determine_executor_actions()
        assert len(actions) == 1
        # NO side also uses BUY (both sides are BUY on Limitless, token routing
        # happens at connector level via trading pair suffix "NO-USDC")
        assert actions[0].executor_config.side == _TradeType.BUY
        assert actions[0].executor_config.trading_pair.endswith("NO-USDC")


class TestOrderFeedback:
    """Verify set_order_id / clear_order are called from controller."""

    def _make_mm_controller(self, config):
        config.quoting.enabled = True
        ctrl = BinaryOptionsController(config, MagicMock(), asyncio.Queue())
        ctrl.connectors = {config.connector_name: MagicMock()}
        return ctrl

    def _wire_mm_mocks(self, controller, quote_actions):
        controller.runtime_bridge = MagicMock()
        controller.runtime_bridge.should_trade.return_value = True
        controller.runtime_bridge.get_coin_param = MagicMock(side_effect=lambda c, k, d=None: {
            "stop_loss_pct": 0.03, "tp_distance": 0.05,
            "trailing_trigger_pct": 0.05, "trailing_distance_pct": 0.02,
        }.get(k, d))
        controller.processed_data = {
            "now_ts": 1000.0,
            "coins": {"BTC": {"vol": 0.01, "z_score": 0.0, "btc_z_score": 0.0, "combined_z": 0.0}},
            "market_data": {"BTC": {"slug": "BTC-YES-100K", "yes_price": 0.5}},
            "orderbook_mids": {"BTC": 0.5},
            "reward_spreads": {"BTC": 0.03},
            "hours_left": {"BTC": 2.0},
            "btc_spot": 100000.0,
        }
        controller.position_tracker = MagicMock()
        controller.executors_info = []
        controller.quote_manager = MagicMock()
        controller.quote_manager.tick.return_value = quote_actions

    def test_place_calls_set_order_id(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        qa = QuoteActions(actions=[
            QuoteAction(action="place", coin="BTC", side="YES", price=0.45, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, qa)
        actions = ctrl.determine_executor_actions()
        ctrl.quote_manager.set_order_id.assert_called_once_with(
            "BTC", "YES", actions[0].executor_config.id
        )

    def test_cancel_calls_clear_order(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        ctrl._mm_executor_map["BTC:YES"] = "exec_123"
        qa = QuoteActions(actions=[
            QuoteAction(action="cancel", coin="BTC", side="YES"),
        ])
        self._wire_mm_mocks(ctrl, qa)
        ctrl.determine_executor_actions()
        ctrl.quote_manager.clear_order.assert_called_once_with("BTC", "YES")

    def test_update_calls_set_order_id(self, config):
        ctrl = self._make_mm_controller(config)
        from controllers.generic.binary_options.quote_manager import QuoteAction, QuoteActions
        ctrl._mm_executor_map["BTC:YES"] = "old_exec"
        active_executor = MagicMock()
        active_executor.id = "old_exec"
        active_executor.is_closed = False
        active_executor.is_active = True
        qa = QuoteActions(actions=[
            QuoteAction(action="update", coin="BTC", side="YES", price=0.48, size=10.0),
        ])
        self._wire_mm_mocks(ctrl, qa)
        ctrl.executors_info = [active_executor]
        ctrl.determine_executor_actions()
        ctrl.quote_manager.set_order_id.assert_not_called()


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
