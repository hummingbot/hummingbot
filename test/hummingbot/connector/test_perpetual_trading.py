import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import MagicMock

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.data_type.common import PositionMode, PositionSide
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate


class PerpetualTest(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.perpetual_trading = PerpetualTrading([self.trading_pair])
        self.perpetual_trading.logger().setLevel(1)
        self.perpetual_trading.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    async def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_init(self):
        self.assertEqual(len(self.perpetual_trading.account_positions), 0)
        self.assertEqual(self.perpetual_trading.position_mode, PositionMode.ONEWAY)
        self.assertEqual(self.perpetual_trading.funding_payment_span, [0, 0])

    def test_account_positions(self):
        """
        Test getting account positions by manually adding a position to the class member
        """
        a_pos: Position = Position(
            "market1", PositionSide.LONG, Decimal("0"), Decimal("100"), Decimal("1"), Decimal("5")
        )
        self.perpetual_trading._account_positions["market1"] = a_pos
        self.assertEqual(len(self.perpetual_trading.account_positions), 1)
        self.assertEqual(self.perpetual_trading.account_positions["market1"], a_pos)
        self.assertEqual(self.perpetual_trading.get_position("market1"), a_pos)
        self.assertEqual(self.perpetual_trading.get_position("market2"), None)

    def test_position_key(self):
        self.perpetual_trading.set_position_mode(PositionMode.ONEWAY)
        self.assertEqual(self.perpetual_trading.position_key("market1"), "market1")
        self.assertEqual(self.perpetual_trading.position_key("market1", PositionSide.LONG), "market1")
        self.perpetual_trading.set_position_mode(PositionMode.HEDGE)
        self.assertEqual(self.perpetual_trading.position_key("market1", PositionSide.LONG), "market1LONG")
        self.assertEqual(self.perpetual_trading.position_key("market1", PositionSide.SHORT), "market1SHORT")

    def test_position_mode(self):
        self.assertEqual(self.perpetual_trading.position_mode, PositionMode.ONEWAY)
        self.perpetual_trading.set_position_mode(PositionMode.HEDGE)
        self.assertEqual(self.perpetual_trading.position_mode, PositionMode.HEDGE)

    def test_leverage(self):
        self.perpetual_trading.set_leverage("pair1", 2)
        self.perpetual_trading.set_leverage("pair2", 3)
        self.assertEqual(self.perpetual_trading.get_leverage("pair1"), 2)
        self.assertEqual(self.perpetual_trading.get_leverage("pair2"), 3)

    def test_funding_info(self):
        """
        Test getting funding infos by manually adding a funding info to the class member
        """
        fInfo: FundingInfo = FundingInfo("pair1", Decimal(1), Decimal(2), 1000, Decimal(0.1))
        self.perpetual_trading._funding_info["pair1"] = fInfo
        self.assertEqual(self.perpetual_trading.get_funding_info("pair1"), fInfo)

    def test_funding_info_initialization(self):
        self.assertFalse(self.perpetual_trading.is_funding_info_initialized())

        funding_info = FundingInfo(
            self.trading_pair,
            index_price=Decimal("1"),
            mark_price=Decimal("2"),
            next_funding_utc_timestamp=3,
            rate=Decimal("4"),
        )
        self.perpetual_trading.initialize_funding_info(funding_info)

        self.assertTrue(self.perpetual_trading.is_funding_info_initialized())
        self.assertEqual(1, len(self.perpetual_trading.funding_info))

    def test_updating_funding_info_logs_exception(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = [
            self._create_exception_and_unlock_test_with_event(
                RuntimeError("Some error")
            ),
            asyncio.CancelledError(),
        ]
        self.perpetual_trading._funding_info_stream = mock_queue
        self.perpetual_trading.start()
        self.listening_task = self.perpetual_trading._funding_info_updater_task

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.perpetual_trading.stop()

        self.assertTrue(self._is_logged("ERROR", "Unexpected error updating funding info."))

    def test_updating_funding_info_success(self):
        self.perpetual_trading.start()

        funding_info = FundingInfo(
            self.trading_pair,
            index_price=Decimal("1"),
            mark_price=Decimal("2"),
            next_funding_utc_timestamp=3,
            rate=Decimal("4"),
        )
        self.perpetual_trading.initialize_funding_info(funding_info)

        self.assertEqual(Decimal("1"), self.perpetual_trading.funding_info[self.trading_pair].index_price)

        funding_info_update = FundingInfoUpdate(self.trading_pair, index_price=Decimal("10"))

        async def return_update():
            return funding_info_update

        mock_queue = MagicMock()
        mock_queue.get.side_effect = [
            return_update(),
            asyncio.CancelledError(),
        ]
        self.perpetual_trading._funding_info_stream = mock_queue
        self.listening_task = self.perpetual_trading._funding_info_updater_task

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.perpetual_trading.funding_info[self.trading_pair].index_price)
