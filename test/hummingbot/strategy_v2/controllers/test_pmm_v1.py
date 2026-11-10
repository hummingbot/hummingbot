import asyncio
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from controllers.generic.pmm_v1 import PMMV1, PMMV1Config
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class TestPMMV1(unittest.TestCase):
    def setUp(self):
        self.config = PMMV1Config(
            id="test_pmm",
            connector_name="binance",
            trading_pair="ETH-USDT",
            order_amount=Decimal("1"),
            buy_spreads=[0.01],
            sell_spreads=[0.01],
            order_refresh_time=30,
            filled_order_delay=60,
        )
        self.market_data_provider = MagicMock(spec=MarketDataProvider)
        self.market_data_provider.time.return_value = 1000.0
        self.market_data_provider.get_price_by_type.return_value = Decimal("2000")
        self.actions_queue = asyncio.Queue()
        self.controller = PMMV1(
            config=self.config,
            market_data_provider=self.market_data_provider,
            actions_queue=self.actions_queue,
        )

    def test_filled_order_delay_not_retriggered_on_subsequent_refresh(self):
        # Step 1: Active executor for buy_0
        exec_1 = MagicMock(spec=ExecutorInfo)
        exec_1.id = "exec_1"
        exec_1.custom_info = {"level_id": "buy_0"}
        exec_1.is_active = True
        exec_1.close_type = None

        self.controller.executors_info = [exec_1]
        self.controller._detect_filled_executors()
        # Not yet filled, level should have no delay
        self.assertNotIn("buy_0", self.controller._level_next_create_timestamps)

        # Step 2: exec_1 fills (POSITION_HOLD)
        exec_1.is_active = False
        exec_1.close_type = CloseType.POSITION_HOLD

        self.market_data_provider.time.return_value = 1030.0
        self.controller.executors_info = [exec_1]
        self.controller._detect_filled_executors()

        # Filled order delay applied: 1030 + 60 = 1090
        self.assertEqual(1090.0, self.controller._level_next_create_timestamps["buy_0"])

        # Step 3: Advance time past delay, new executor exec_2 is active
        self.market_data_provider.time.return_value = 1100.0
        exec_2 = MagicMock(spec=ExecutorInfo)
        exec_2.id = "exec_2"
        exec_2.custom_info = {"level_id": "buy_0"}
        exec_2.is_active = True
        exec_2.close_type = None

        # Both exec_1 (completed) and exec_2 (active) are in executors_info
        self.controller.executors_info = [exec_1, exec_2]
        self.controller._detect_filled_executors()

        # Step 4: exec_2 is cancelled by order refresh (EARLY_STOP), NOT filled
        exec_2.is_active = False
        exec_2.close_type = CloseType.EARLY_STOP

        self.market_data_provider.time.return_value = 1130.0
        self.controller.executors_info = [exec_1, exec_2]
        self.controller._detect_filled_executors()

        # BUG CHECK: Under the bug, exec_1's POSITION_HOLD would cause buy_0
        # to re-trigger filled_order_delay to 1130 + 60 = 1190.
        # With the fix, exec_2 was cancelled, so timestamp remains unchanged (1090.0).
        self.assertEqual(1090.0, self.controller._level_next_create_timestamps["buy_0"])
