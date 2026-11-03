import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from controllers.generic.pmm_v1 import PMMV1, PMMV1Config
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.models.executors import CloseType


class TestPMMV1FilledOrderDelay(TestCase):
    """Unit tests for PMM V1 filled-executor detection (#8527)."""

    def _make_controller(self, **config_overrides) -> PMMV1:
        config_kwargs = dict(
            id="test_pmm_v1",
            connector_name="bitget",
            trading_pair="SOL-USDT",
            order_amount=Decimal("0.03"),
            buy_spreads=[Decimal("0.001")],
            sell_spreads=[Decimal("0.001")],
            order_refresh_time=30,
            order_refresh_tolerance_pct=Decimal("-1"),
            filled_order_delay=60,
        )
        config_kwargs.update(config_overrides)
        config = PMMV1Config(**config_kwargs)

        market_data_provider = MagicMock(spec=MarketDataProvider)
        market_data_provider.time.return_value = 1000.0
        actions_queue = AsyncMock(spec=asyncio.Queue)

        controller = PMMV1(
            config=config,
            market_data_provider=market_data_provider,
            actions_queue=actions_queue,
        )
        controller.executors_info = []
        controller.positions_held = []
        controller.processed_data = {"reference_price": Decimal("100")}
        return controller

    @staticmethod
    def _make_executor_info(
        executor_id: str,
        level_id: str,
        is_active: bool,
        close_type: CloseType = None,
    ):
        executor = MagicMock()
        executor.id = executor_id
        executor.is_active = is_active
        executor.close_type = close_type
        executor.custom_info = {"level_id": level_id}
        return executor

    def test_filled_order_delay_applied_when_active_executor_fills(self):
        controller = self._make_controller(filled_order_delay=60)

        # Tick 1 (t=1000): buy_0 is active
        buy_exec_1 = self._make_executor_info("buy-exec-1", "buy_0", is_active=True)
        controller.executors_info = [buy_exec_1]
        controller._detect_filled_executors()
        self.assertNotIn("buy_0", controller._level_next_create_timestamps)

        # Tick 2 (t=1015): buy-exec-1 fills (POSITION_HOLD)
        controller.market_data_provider.time.return_value = 1015.0
        buy_exec_1.is_active = False
        buy_exec_1.close_type = CloseType.POSITION_HOLD
        controller._detect_filled_executors()

        self.assertEqual(controller._level_next_create_timestamps.get("buy_0"), 1075.0)

    def test_filled_order_delay_not_reapplied_on_refresh_after_prior_fill(self):
        controller = self._make_controller(filled_order_delay=60)

        # Tick 1 (t=1000): buy_0 and sell_0 active
        buy_exec_1 = self._make_executor_info("buy-exec-1", "buy_0", is_active=True)
        sell_exec_1 = self._make_executor_info("sell-exec-1", "sell_0", is_active=True)
        controller.executors_info = [buy_exec_1, sell_exec_1]
        controller._detect_filled_executors()

        # Tick 2 (t=1010): buy-exec-1 fills (POSITION_HOLD)
        controller.market_data_provider.time.return_value = 1010.0
        buy_exec_1.is_active = False
        buy_exec_1.close_type = CloseType.POSITION_HOLD
        controller._detect_filled_executors()
        self.assertEqual(controller._level_next_create_timestamps["buy_0"], 1070.0)

        # Tick 3 (t=1070): delay expires and buy-exec-2 becomes active; historical buy-exec-1 stays in executors_info
        controller.market_data_provider.time.return_value = 1070.0
        buy_exec_2 = self._make_executor_info("buy-exec-2", "buy_0", is_active=True)
        controller.executors_info = [buy_exec_1, sell_exec_1, buy_exec_2]
        controller._detect_filled_executors()

        # Tick 4 (t=1100): buy-exec-2 refreshes after 30s without filling (EARLY_STOP)
        controller.market_data_provider.time.return_value = 1100.0
        buy_exec_2.is_active = False
        buy_exec_2.close_type = CloseType.EARLY_STOP
        controller._detect_filled_executors()

        # Timestamp must remain 1070.0 (not pushed to 1160.0 by historical buy-exec-1)
        self.assertEqual(controller._level_next_create_timestamps["buy_0"], 1070.0)
        self.assertIn("buy_0", controller.get_levels_to_execute())

    def test_filled_order_delay_reapplied_when_subsequent_executor_fills(self):
        controller = self._make_controller(filled_order_delay=60)

        # First fill on buy_0 at t=1010
        buy_exec_1 = self._make_executor_info("buy-exec-1", "buy_0", is_active=True)
        controller.executors_info = [buy_exec_1]
        controller._detect_filled_executors()

        controller.market_data_provider.time.return_value = 1010.0
        buy_exec_1.is_active = False
        buy_exec_1.close_type = CloseType.POSITION_HOLD
        controller._detect_filled_executors()
        self.assertEqual(controller._level_next_create_timestamps["buy_0"], 1070.0)

        # Second executor on buy_0 refreshes unfilled at t=1100
        controller.market_data_provider.time.return_value = 1070.0
        buy_exec_2 = self._make_executor_info("buy-exec-2", "buy_0", is_active=True)
        controller.executors_info = [buy_exec_1, buy_exec_2]
        controller._detect_filled_executors()

        controller.market_data_provider.time.return_value = 1100.0
        buy_exec_2.is_active = False
        buy_exec_2.close_type = CloseType.EARLY_STOP
        controller._detect_filled_executors()
        self.assertEqual(controller._level_next_create_timestamps["buy_0"], 1070.0)

        # Third executor on buy_0 is placed at t=1101 and fills at t=1120
        controller.market_data_provider.time.return_value = 1101.0
        buy_exec_3 = self._make_executor_info("buy-exec-3", "buy_0", is_active=True)
        controller.executors_info = [buy_exec_1, buy_exec_2, buy_exec_3]
        controller._detect_filled_executors()

        controller.market_data_provider.time.return_value = 1120.0
        buy_exec_3.is_active = False
        buy_exec_3.close_type = CloseType.POSITION_HOLD
        controller._detect_filled_executors()
        self.assertEqual(controller._level_next_create_timestamps["buy_0"], 1180.0)
