import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from pydantic import ValidationError

from controllers.generic.pmm_king import PMMKing, PMMKingConfig
from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.executors.data_types import PositionSummary
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class TestPMMKing(IsolatedAsyncioWrapperTestCase):
    connector = "binance"
    pair = "WLD-FDUSD"

    def setUp(self):
        self.config = PMMKingConfig(
            id="test",
            connector_name=self.connector,
            trading_pair=self.pair,
            total_amount_quote=Decimal("1000"),
            curve_prices="0.45,0.55,0.70",
            curve_allocations="0.5,0.35,0.2",
            n_orders_per_side=2,
            min_spread=Decimal("0.002"),
            max_spread=Decimal("0.01"),
            min_order_amount_quote=Decimal("10"),
            max_order_amount_quote=Decimal("65"),
            outer_amount_ratio=Decimal("1.0"),
            spread_capture_pct=Decimal("0.05"),
            convergence_step_pct=Decimal("0.5"),
            price_distance_floor=Decimal("0.3"),
            shift_intensity=Decimal("0"),
            executor_refresh_time=30,
            cooldown_time=5,
            position_mode=PositionMode.ONEWAY,
        )
        self.mock_market_data_provider = MagicMock(spec=MarketDataProvider)
        self.mock_actions_queue = AsyncMock(spec=asyncio.Queue)
        self.controller = PMMKing(
            config=self.config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue,
        )
        self.mock_market_data_provider.quantize_order_amount = MagicMock(
            side_effect=lambda connector, pair, amount: amount)
        self.mock_market_data_provider.time = MagicMock(return_value=1000.0)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _set_mid_price(self, price):
        type(self.mock_market_data_provider).get_price_by_type = MagicMock(
            return_value=Decimal(str(price)))

    def _order_executor_info(self, level_id, side, price, timestamp,
                             status=RunnableStatus.RUNNING, is_active=True,
                             close_timestamp=None):
        config = OrderExecutorConfig(
            timestamp=timestamp,
            connector_name=self.connector,
            trading_pair=self.pair,
            side=side,
            amount=Decimal("1"),
            price=Decimal(str(price)),
            execution_strategy=ExecutionStrategy.LIMIT_MAKER,
            level_id=level_id,
        )
        return ExecutorInfo(
            id=f"{level_id}_id",
            timestamp=timestamp,
            type="order_executor",
            status=status,
            config=config,
            net_pnl_pct=Decimal("0"),
            net_pnl_quote=Decimal("0"),
            cum_fees_quote=Decimal("0"),
            filled_amount_quote=Decimal("0"),
            is_active=is_active,
            is_trading=False,
            custom_info={"level_id": level_id, "side": side},
            close_timestamp=close_timestamp,
        )

    def _position(self, amount, breakeven, upnl=Decimal("0"), rpnl=Decimal("0"), fees=Decimal("0")):
        """amount_quote = amount * breakeven, which drives current_base_pct."""
        return PositionSummary(
            connector_name=self.connector,
            trading_pair=self.pair,
            volume_traded_quote=Decimal("0"),
            side=TradeType.BUY,
            amount=Decimal(str(amount)),
            breakeven_price=Decimal(str(breakeven)),
            unrealized_pnl_quote=Decimal(str(upnl)),
            realized_pnl_quote=Decimal(str(rpnl)),
            cum_fees_quote=Decimal(str(fees)),
        )

    async def _prime(self, mid_price, positions=None):
        self._set_mid_price(mid_price)
        self.controller.positions_held = positions or []
        await self.controller.update_processed_data()
        return self.controller.processed_data

    # ── interpolation ─────────────────────────────────────────────────────

    def test_interpolate_target_allocation(self):
        prices = [0.45, 0.55, 0.70]
        allocs = [0.5, 0.35, 0.20]
        interp = PMMKing.interpolate_target_allocation
        self.assertEqual(interp(0.40, prices, allocs), Decimal("0.5"))   # below -> clamp
        self.assertEqual(interp(0.80, prices, allocs), Decimal("0.2"))   # above -> clamp
        self.assertEqual(interp(0.55, prices, allocs), Decimal("0.35"))  # breakpoint
        # midpoint of [0.45, 0.55] -> midpoint of [0.5, 0.35] (float-noisy, hence almost)
        self.assertAlmostEqual(float(interp(0.50, prices, allocs)), 0.425, places=6)

    # ── config validation ─────────────────────────────────────────────────

    def test_curve_length_mismatch_raises(self):
        with self.assertRaises(ValidationError):
            PMMKingConfig(id="t", curve_prices="0.4,0.5,0.6", curve_allocations="1.0,0.5")

    def test_curve_non_increasing_raises(self):
        with self.assertRaises(ValidationError):
            PMMKingConfig(id="t", curve_prices="0.5,0.5,0.6", curve_allocations="1.0,0.5,0.2")

    def test_curve_alloc_out_of_range_raises(self):
        with self.assertRaises(ValidationError):
            PMMKingConfig(id="t", curve_prices="0.4,0.6", curve_allocations="1.0,1.5")

    def test_position_mode_validator(self):
        self.assertEqual(PMMKingConfig.validate_position_mode("ONEWAY"), PositionMode.ONEWAY)
        with self.assertRaises(ValueError):
            PMMKingConfig.validate_position_mode("not_a_mode")

    def test_removed_fields_are_rejected(self):
        # extra="forbid": legacy barrier + old sizing knobs are a hard error.
        for bad in ("take_profit", "stop_loss", "portfolio_allocation",
                    "amount_skew_intensity", "spread_factor"):
            with self.assertRaises(ValidationError, msg=f"{bad} should be rejected"):
                PMMKingConfig(id="t", **{bad: "0.5"})

    # ── processed data / sizing model ─────────────────────────────────────

    async def test_processed_data_keys_and_pnl(self):
        pd = await self._prime(0.55, [self._position(700, 0.5, upnl=12, rpnl=34, fees=2)])
        self.assertEqual(pd["current_base_pct"], Decimal("0.35"))  # 700*0.5/1000
        self.assertEqual(pd["target_base_pct"], Decimal("0.35"))
        self.assertEqual(pd["gap_pct"], Decimal("0"))
        self.assertEqual(pd["realized_pnl_quote"], Decimal("34"))
        self.assertEqual(pd["global_pnl_quote"], Decimal("44"))  # 12 + 34 - 2

    async def test_no_overshoot_at_target_quotes_only_band(self):
        pd = await self._prime(0.55, [self._position(700, 0.5)])  # current == target == 35%
        self.assertEqual(pd["gap_pct"], Decimal("0"))
        self.assertEqual(pd["convergence_quote"], Decimal("0"))
        band = pd["band_quote"]
        self.assertEqual(pd["buy_budget"], band)
        self.assertEqual(pd["sell_budget"], band)

    async def test_no_sells_without_held_inventory(self):
        # Empty POSITION_HOLD ledger -> the band must not place sells against the
        # account's pre-existing balance.
        pd = await self._prime(0.50, [])  # nothing held
        self.assertEqual(pd["held_base_quote"], Decimal("0"))
        self.assertEqual(pd["sell_budget"], Decimal("0"))
        self.assertGreater(pd["buy_budget"], Decimal("0"))  # still accumulates via buys

    async def test_no_sell_actions_without_held_inventory(self):
        await self._prime(0.50, [])
        self.controller.executors_info = []
        actions = self.controller.determine_executor_actions()
        sides = {a.executor_config.side for a in actions if isinstance(a, CreateExecutorAction)}
        self.assertNotIn(TradeType.SELL, sides)
        self.assertIn(TradeType.BUY, sides)

    async def test_sell_budget_capped_by_held_inventory(self):
        # Held base worth less than the band -> sells capped at what's held.
        # 40 base * 0.55 mid = 22 quote held; band would be 50.
        pd = await self._prime(0.55, [self._position(40, 0.5)])
        self.assertEqual(pd["held_base_quote"], Decimal("22.00"))  # 40 * 0.55
        self.assertLessEqual(pd["sell_budget"], pd["held_base_quote"])

    async def test_gap_drives_convergence_side(self):
        pd = await self._prime(0.50, [self._position(200, 0.5)])  # current 10% < target 42.5%
        self.assertGreater(pd["gap_pct"], Decimal("0"))
        self.assertEqual(pd["convergence_side"], TradeType.BUY)
        self.assertGreater(pd["buy_budget"], pd["band_quote"])
        self.assertEqual(pd["sell_budget"], pd["band_quote"])  # away side = band only

    async def test_over_allocated_converges_with_sells(self):
        pd = await self._prime(0.70, [self._position(1200, 0.5)])  # current 60% > target 20%
        self.assertLess(pd["gap_pct"], Decimal("0"))
        self.assertEqual(pd["convergence_side"], TradeType.SELL)
        self.assertGreater(pd["sell_budget"], pd["band_quote"])
        self.assertEqual(pd["buy_budget"], pd["band_quote"])

    async def test_convergence_never_exceeds_gap(self):
        # The core invariant: convergence_quote <= |gap| * total for any state.
        for mid, amt, be in [(0.50, 0, 0.5), (0.46, 200, 0.5), (0.60, 1000, 0.5), (0.40, 100, 0.5)]:
            pos = [self._position(amt, be)] if amt else []
            pd = await self._prime(mid, pos)
            max_conv = abs(pd["gap_pct"]) * self.config.total_amount_quote
            self.assertLessEqual(pd["convergence_quote"], max_conv + Decimal("1e-9"),
                                 msg=f"overshoot at mid={mid}")

    async def test_inventory_shift(self):
        self.config.shift_intensity = Decimal("0.02")
        # Under target (need base) -> reference pushed above the mid.
        pd = await self._prime(0.50, [])
        self.assertGreater(pd["gap_pct"], Decimal("0"))
        self.assertGreater(pd["ref_price"], pd["mid_price"])
        # Over target (too much base) -> reference pushed below the mid.
        pd = await self._prime(0.55, [self._position(1000, 0.6)])  # current 60% > target 35%
        self.assertLess(pd["gap_pct"], Decimal("0"))
        self.assertLess(pd["ref_price"], pd["mid_price"])
        # shift_intensity = 0 -> reference is the mid.
        self.config.shift_intensity = Decimal("0")
        pd = await self._prime(0.50, [])
        self.assertEqual(pd["ref_price"], pd["mid_price"])

    async def test_price_factor_floor_mid_segment_full_near_breakpoint(self):
        mid_seg = await self._prime(0.50)  # exact midpoint of [0.45, 0.55]
        self.assertEqual(mid_seg["price_factor"], self.config.price_distance_floor)
        near_bp = await self._prime(0.46)  # close to the 0.45 breakpoint
        self.assertGreater(near_bp["price_factor"], Decimal("0.8"))
        outside = await self._prime(0.40)  # below the curve -> full aggressiveness
        self.assertEqual(outside["price_factor"], Decimal("1"))

    async def test_bottom_edge_converge_and_stop(self):
        # Below the curve and already at the (clamped) target -> band off, fully stop.
        pd = await self._prime(0.40, [self._position(1000, 0.5)])  # current 50% == target 50%
        self.assertTrue(pd["outside_curve"])
        self.assertEqual(pd["target_base_pct"], Decimal("0.5"))
        self.assertEqual(pd["convergence_quote"], Decimal("0"))
        self.assertEqual(pd["band_quote"], Decimal("0"))
        self.assertEqual(pd["buy_budget"], Decimal("0"))
        self.assertEqual(pd["sell_budget"], Decimal("0"))

    async def test_outside_curve_converges_without_band(self):
        # Below the curve, needs base -> only convergence buys, no symmetric band.
        pd = await self._prime(0.40, [self._position(200, 0.5)])  # current 10% < target 50%
        self.assertTrue(pd["outside_curve"])
        self.assertEqual(pd["band_quote"], Decimal("0"))
        self.assertEqual(pd["convergence_side"], TradeType.BUY)
        self.assertGreater(pd["buy_budget"], Decimal("0"))
        self.assertEqual(pd["sell_budget"], Decimal("0"))  # no band on the away side

    async def test_outside_curve_at_target_places_no_orders(self):
        await self._prime(0.80, [self._position(400, 0.5)])  # above curve, current 20% == target 20%
        self.controller.executors_info = []
        actions = self.controller.determine_executor_actions()
        creates = [a for a in actions if isinstance(a, CreateExecutorAction)]
        self.assertEqual(creates, [])

    # ── executor actions ──────────────────────────────────────────────────

    async def test_determine_actions_creates_order_executor_configs(self):
        await self._prime(0.50, [self._position(200, 0.5)])  # buys converge + band both sides
        self.controller.executors_info = []
        actions = self.controller.determine_executor_actions()
        creates = [a for a in actions if isinstance(a, CreateExecutorAction)]
        self.assertTrue(creates)
        mid = self.controller.processed_data["mid_price"]
        for a in creates:
            cfg = a.executor_config
            self.assertIsInstance(cfg, OrderExecutorConfig)
            self.assertEqual(cfg.execution_strategy, ExecutionStrategy.LIMIT_MAKER)
            if cfg.side == TradeType.BUY:
                self.assertLess(cfg.price, mid)
            else:
                self.assertGreater(cfg.price, mid)

    async def test_band_quotes_both_sides_at_target(self):
        await self._prime(0.55, [self._position(700, 0.5)])  # gap == 0
        self.controller.executors_info = []
        actions = self.controller.determine_executor_actions()
        sides = {a.executor_config.side for a in actions if isinstance(a, CreateExecutorAction)}
        self.assertEqual(sides, {TradeType.BUY, TradeType.SELL})

    async def test_outermost_buy_at_max_spread(self):
        await self._prime(0.50, [self._position(200, 0.5)])
        self.controller.executors_info = []
        actions = self.controller.determine_executor_actions()
        buy_prices = sorted(a.executor_config.price for a in actions
                            if isinstance(a, CreateExecutorAction) and a.executor_config.side == TradeType.BUY)
        # Tight grid: outermost buy sits at max_spread (1%) from mid, NOT at the breakpoint.
        self.assertAlmostEqual(float(buy_prices[0]), 0.50 * (1 - 0.01), places=4)
        self.assertGreater(float(buy_prices[0]), 0.49)  # nowhere near the 0.45 breakpoint

    async def test_convergence_throttled_by_step(self):
        # Big gap, but convergence is capped at convergence_step_pct * total per cycle.
        self.config.convergence_step_pct = Decimal("0.03")  # 30 quote cap
        pd = await self._prime(0.46, [])  # far below target, price near breakpoint (pf high)
        self.assertEqual(pd["convergence_quote"], Decimal("30.0"))  # capped, not the full gap

    async def test_no_duplicate_quote_when_level_active(self):
        await self._prime(0.50, [self._position(200, 0.5)])
        self.controller.executors_info = [
            self._order_executor_info("buy_0", TradeType.BUY, 0.49, timestamp=1000.0)]
        actions = self.controller.determine_executor_actions()
        created_levels = [a.executor_config.level_id for a in actions
                          if isinstance(a, CreateExecutorAction)]
        self.assertNotIn("buy_0", created_levels)

    async def test_refresh_stops_stale_order(self):
        await self._prime(0.50, [self._position(200, 0.5)])
        self.controller.executors_info = [
            self._order_executor_info("buy_0", TradeType.BUY, 0.49, timestamp=1000.0 - 31)]
        actions = self.controller.determine_executor_actions()
        stops = [a for a in actions if isinstance(a, StopExecutorAction)]
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0].executor_id, "buy_0_id")
        self.assertTrue(stops[0].keep_position)

    async def test_fresh_order_not_refreshed(self):
        await self._prime(0.50, [self._position(200, 0.5)])
        self.controller.executors_info = [
            self._order_executor_info("buy_0", TradeType.BUY, 0.49, timestamp=1000.0 - 5)]
        stops = [a for a in self.controller.determine_executor_actions()
                 if isinstance(a, StopExecutorAction)]
        self.assertEqual(len(stops), 0)

    async def test_cooldown_blocks_recently_terminated_level(self):
        await self._prime(0.50, [self._position(200, 0.5)])
        self.controller.executors_info = [
            self._order_executor_info("buy_1", TradeType.BUY, 0.46, timestamp=1000.0 - 50,
                                      status=RunnableStatus.TERMINATED, is_active=False,
                                      close_timestamp=1000.0 - 1)]
        created = [a.executor_config.level_id for a in self.controller.determine_executor_actions()
                   if isinstance(a, CreateExecutorAction)]
        self.assertNotIn("buy_1", created)

        self.controller.executors_info = [
            self._order_executor_info("buy_1", TradeType.BUY, 0.46, timestamp=1000.0 - 50,
                                      status=RunnableStatus.TERMINATED, is_active=False,
                                      close_timestamp=1000.0 - 10)]
        created = [a.executor_config.level_id for a in self.controller.determine_executor_actions()
                   if isinstance(a, CreateExecutorAction)]
        self.assertIn("buy_1", created)

    # ── sizing helpers ────────────────────────────────────────────────────

    def test_distribute_budget_scales_levels_with_size(self):
        # Below the per-order minimum -> nothing placed.
        self.assertEqual(self.controller._distribute_budget(Decimal("5")), [])
        # 25 / min 10 -> k=2, two equal levels of 12.5 (ratio=1.0 in setUp).
        self.assertEqual(self.controller._distribute_budget(Decimal("25")), [Decimal("12.5"), Decimal("12.5")])
        # Large budget caps at n_orders_per_side (2) and at max_order (65).
        amounts = self.controller._distribute_budget(Decimal("500"))
        self.assertEqual(len(amounts), 2)
        for a in amounts:
            self.assertLessEqual(a, Decimal("65"))

    def test_distribute_budget_outer_heavy(self):
        # ratio>1 -> amounts increase with distance (outer order bigger), each >= min.
        self.config.outer_amount_ratio = Decimal("3.0")
        amounts = self.controller._distribute_budget(Decimal("60"))
        self.assertEqual(len(amounts), 2)  # n_orders_per_side
        self.assertLess(amounts[0], amounts[-1])               # outer > inner
        self.assertGreaterEqual(amounts[0], self.config.min_order_amount_quote)
        self.assertAlmostEqual(float(sum(amounts)), 60.0, places=6)  # conserves budget
        # outer should be ~3x the inner
        self.assertAlmostEqual(float(amounts[-1] / amounts[0]), 3.0, places=4)

    def test_side_spreads_linear_between_min_and_max(self):
        spreads = self.controller._side_spreads(3, Decimal("0.01"))
        self.assertEqual(spreads[0], Decimal("0.002"))   # inner = min_spread
        self.assertEqual(spreads[-1], Decimal("0.01"))   # outer = max_spread
        # single level -> just the inner spread
        self.assertEqual(self.controller._side_spreads(1, Decimal("0.01")), [Decimal("0.002")])

    # ── price fallbacks ───────────────────────────────────────────────────

    async def test_mid_price_none_falls_back_to_last_known(self):
        self.controller.processed_data = {"mid_price": Decimal("0.52")}
        type(self.mock_market_data_provider).get_price_by_type = MagicMock(return_value=None)
        self.controller.positions_held = []
        await self.controller.update_processed_data()
        self.assertEqual(self.controller.processed_data["mid_price"], Decimal("0.52"))

    async def test_mid_price_exception_falls_back(self):
        self.controller.processed_data = {}
        type(self.mock_market_data_provider).get_price_by_type = MagicMock(side_effect=Exception("boom"))
        self.controller.positions_held = []
        await self.controller.update_processed_data()
        self.assertEqual(self.controller.processed_data["mid_price"], Decimal("100"))

    # ── per-tick recompute (backtester precompute-once safety) ────────────

    def test_determine_recomputes_position_state_per_tick(self):
        """determine_executor_actions must recompute position-dependent state itself, because
        the backtester calls update_processed_data only ONCE. A held position appearing
        between ticks must be reflected without a separate update_processed_data() call —
        otherwise the controller stays frozen at its tick-0 state (no position, never sells)."""
        self._set_mid_price("0.55")

        # No position: recompute -> flat, nothing to sell.
        self.controller.positions_held = []
        self.controller.executors_info = []
        self.controller.determine_executor_actions()
        self.assertEqual(self.controller.processed_data["current_base_pct"], Decimal("0"))
        self.assertEqual(self.controller.processed_data["sell_budget"], Decimal("0"))

        # A held long shows up (fills accumulated). determine must see it on the next tick
        # with no update_processed_data() call in between.
        self.controller.positions_held = [self._position(600, 0.55)]
        self.controller.determine_executor_actions()
        self.assertGreater(self.controller.processed_data["current_base_pct"], Decimal("0"))
        self.assertGreater(self.controller.processed_data["sell_budget"], Decimal("0"))

    def test_recompute_preserves_precomputed_features(self):
        """The per-tick recompute updates processed_data in place, so the backtester's
        precomputed 'features' frame survives across ticks."""
        self._set_mid_price("0.55")
        self.controller.positions_held = []
        self.controller.executors_info = []
        self.controller.processed_data = {"features": "SENTINEL"}
        self.controller.determine_executor_actions()
        self.assertEqual(self.controller.processed_data["features"], "SENTINEL")
        self.assertIn("current_base_pct", self.controller.processed_data)

    # ── status display ────────────────────────────────────────────────────

    def test_format_status_initializing(self):
        self.controller.processed_data = {}
        lines = self.controller.to_format_status()
        self.assertTrue(any("Initializing" in ln for ln in lines))

    async def test_format_status_renders_model(self):
        await self._prime(0.50, [self._position(200, 0.5, upnl=12, rpnl=34, fees=2)])
        self.controller.executors_info = [
            self._order_executor_info("buy_0", TradeType.BUY, 0.49, timestamp=990.0)]
        text = "\n".join(self.controller.to_format_status())
        for token in ("Inventory", "Gap", "rPnL", "Held", "allocation curve", "MID", "Exposure", "0.4900"):
            self.assertIn(token, text)
