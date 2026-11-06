import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from controllers.generic.pmm_mister import PMMister, PMMisterConfig
from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider


class TestPMMisterGlobalCloseCooldown(TestCase):
    """Unit tests for the `_global_close_cooling_down` flag added for issue #8346.

    The flag prevents immediate TP/SL re-triggering right after a successful global
    position close, because `processed_data["position_amount"]` lags the real exchange
    position by one or more ticks.
    """

    def _make_controller(self, **config_overrides) -> PMMister:
        config_kwargs = dict(
            id="test",
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
        )
        config_kwargs.update(config_overrides)
        config = PMMisterConfig(**config_kwargs)

        market_data_provider = MagicMock(spec=MarketDataProvider)
        actions_queue = AsyncMock(spec=asyncio.Queue)

        controller = PMMister(
            config=config,
            market_data_provider=market_data_provider,
            actions_queue=actions_queue,
        )
        # Sensible defaults; individual tests override as needed.
        controller.executors_info = []
        controller.positions_held = []
        controller.processed_data = {}
        return controller

    def _make_position(self, side: TradeType = TradeType.BUY,
                       connector_name: str = "binance_perpetual",
                       trading_pair: str = "ETH-USDT"):
        position = MagicMock()
        position.side = side
        position.connector_name = connector_name
        position.trading_pair = trading_pair
        return position

    # ── 1. Close confirms (exchange=0) → cooling down True, phase None ──────

    def test_close_done_sets_cooling_down_and_clears_phase(self):
        controller = self._make_controller()
        controller._global_close_phase = "closing"
        controller._global_close_side = TradeType.BUY
        controller._global_close_retries = 1
        controller._global_close_cooling_down = False
        # No active close executors so the closing branch reads the exchange position.
        controller.executors_info = []
        # Exchange reports the position is fully closed.
        controller._get_exchange_position = MagicMock(return_value=(Decimal("0"), None))

        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        self.assertTrue(controller._global_close_cooling_down)
        self.assertIsNone(controller._global_close_phase)
        self.assertIsNone(controller._global_close_side)
        self.assertEqual(controller._global_close_retries, 0)

    # ── 2. Core #8346 regression: stale position_amount>0, exchange=0 ───────

    def test_cooling_down_suppresses_retrigger_with_stale_data(self):
        controller = self._make_controller(
            global_tp_enabled=True,
            global_tp_activation_from="always",
            global_take_profit=Decimal("0.01"),
        )
        controller._global_close_phase = None
        controller._global_close_retries = 0
        controller._global_close_cooling_down = True
        # Stale processed_data still shows a position and a PnL that WOULD trigger TP.
        controller.processed_data = {
            "position_amount": Decimal("1"),
            "current_base_pct": Decimal("0.5"),
            "unrealized_pnl_pct": Decimal("0.05"),
        }
        # But the exchange already confirms the position is gone.
        controller._get_exchange_position = MagicMock(return_value=(Decimal("0"), None))

        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        # No new close attempt was started.
        self.assertEqual(controller._global_close_retries, 0)
        self.assertIsNone(controller._global_close_phase)
        # Still cooling down until processed_data catches up.
        self.assertTrue(controller._global_close_cooling_down)

    # ── 3. processed_data syncs to 0 → flag clears ─────────────────────────

    def test_cooling_down_clears_when_processed_data_synced(self):
        controller = self._make_controller()
        controller._global_close_phase = None
        controller._global_close_retries = 0
        controller._global_close_cooling_down = True
        controller.processed_data = {"position_amount": Decimal("0")}
        # Exchange position should not even be consulted, but mock it just in case.
        controller._get_exchange_position = MagicMock(return_value=(Decimal("0"), None))

        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        self.assertFalse(controller._global_close_cooling_down)

    # ── 4. Exchange shows a genuinely new position → flag clears, TP evals ──

    def test_cooling_down_clears_when_new_exchange_position_opens(self):
        controller = self._make_controller(
            global_tp_enabled=True,
            global_tp_activation_from="always",
            global_take_profit=Decimal("0.01"),
        )
        controller._global_close_phase = None
        controller._global_close_retries = 0
        controller._global_close_cooling_down = True
        controller.processed_data = {
            "position_amount": Decimal("1"),
            "current_base_pct": Decimal("0.5"),
            "unrealized_pnl_pct": Decimal("0.05"),  # above take_profit → should trigger
        }
        controller.positions_held = [self._make_position(side=TradeType.BUY)]
        controller.executors_info = []
        # Exchange shows a brand-new non-zero position → cooldown no longer applies.
        controller._get_exchange_position = MagicMock(return_value=(Decimal("2"), TradeType.BUY))

        actions = controller._check_global_tp_sl()

        # Cooldown cleared and TP/SL evaluated → entered the stopping phase.
        self.assertFalse(controller._global_close_cooling_down)
        self.assertEqual(controller._global_close_phase, "stopping")
        self.assertIsInstance(actions, list)

    # ── 5. Abort paths do NOT set the cooling-down flag ────────────────────

    def test_abort_retry_limit_does_not_set_cooling_down(self):
        controller = self._make_controller()
        controller._global_close_phase = "closing"
        controller._global_close_side = TradeType.BUY
        controller._global_close_retries = 3  # at the abort limit
        controller._global_close_cooling_down = False
        controller.executors_info = []

        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        self.assertIsNone(controller._global_close_phase)
        self.assertEqual(controller._global_close_retries, 0)
        self.assertFalse(controller._global_close_cooling_down)

    def test_abort_side_flip_does_not_set_cooling_down(self):
        controller = self._make_controller()
        controller._global_close_phase = "closing"
        controller._global_close_side = TradeType.BUY
        controller._global_close_retries = 0
        controller._global_close_cooling_down = False
        controller.executors_info = []
        # Exchange position flipped to the opposite side.
        controller._get_exchange_position = MagicMock(return_value=(Decimal("2"), TradeType.SELL))

        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        self.assertIsNone(controller._global_close_phase)
        self.assertFalse(controller._global_close_cooling_down)

    def test_abort_quantize_to_zero_does_not_set_cooling_down(self):
        controller = self._make_controller()
        controller._global_close_phase = "closing"
        controller._global_close_side = TradeType.BUY
        controller._global_close_retries = 0
        controller._global_close_cooling_down = False
        controller.executors_info = []
        # Non-zero exchange dust that quantizes to zero.
        controller._get_exchange_position = MagicMock(return_value=(Decimal("0.0000001"), TradeType.BUY))
        controller.market_data_provider.quantize_order_amount = MagicMock(return_value=Decimal("0"))

        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        self.assertIsNone(controller._global_close_phase)
        self.assertEqual(controller._global_close_retries, 0)
        self.assertFalse(controller._global_close_cooling_down)

    # ── 6. Spot-like connector (no _perpetual_trading) ─────────────────────

    def test_spot_connector_exchange_position_returns_zero(self):
        controller = self._make_controller()
        # spec=[] → hasattr(connector, '_perpetual_trading') is False.
        spot_connector = MagicMock(spec=[])
        controller.market_data_provider.get_connector = MagicMock(return_value=spot_connector)

        amount, side = controller._get_exchange_position()

        self.assertEqual(amount, Decimal("0"))
        self.assertIsNone(side)

    def test_spot_connector_cooling_down_no_infinite_loop(self):
        controller = self._make_controller()
        controller._global_close_phase = None
        controller._global_close_retries = 0
        controller._global_close_cooling_down = True
        controller.processed_data = {
            "position_amount": Decimal("1"),
            "current_base_pct": Decimal("0.5"),
            "unrealized_pnl_pct": Decimal("0.05"),
        }
        spot_connector = MagicMock(spec=[])
        controller.market_data_provider.get_connector = MagicMock(return_value=spot_connector)

        # Should not raise and should suppress (exchange reads 0 for spot).
        actions = controller._check_global_tp_sl()

        self.assertEqual(actions, [])
        self.assertTrue(controller._global_close_cooling_down)
        self.assertEqual(controller._global_close_retries, 0)
