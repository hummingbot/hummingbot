from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
import asyncio

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
)
from test.mock.mock_perp_connector import MockPerpConnector
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage import SpotPerpetualArbitrageStrategy
from hummingbot.connector.derivative.position import Position, PositionSide


class TestSpotPerpetualArbitrage(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]
    level = 0
    log_records = []

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def setUp(self):
        self.log_records = []
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1, self.start_timestamp, self.end_timestamp)
        self.spot_connector: BacktestMarket = BacktestMarket()
        self.spot_obook: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.spot_obook.set_balanced_order_book(mid_price=100,
                                                min_price=1,
                                                max_price=200,
                                                price_step_size=1,
                                                volume_step_size=10)
        self.spot_connector.add_data(self.spot_obook)
        self.spot_connector.set_balance("HBOT", 500)
        self.spot_connector.set_balance("ETH", 5000)
        self.spot_connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.spot_market_info = MarketTradingPairTuple(self.spot_connector, self.trading_pair,
                                                       self.base_asset, self.quote_asset)

        self.perp_connector: MockPerpConnector = MockPerpConnector()
        self.perp_connector.set_leverage(self.trading_pair, 5)
        self.perp_obook: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset,
                                                                   self.quote_asset)
        self.perp_obook.set_balanced_order_book(mid_price=110,
                                                min_price=1,
                                                max_price=200,
                                                price_step_size=1,
                                                volume_step_size=10)
        self.perp_connector.add_data(self.perp_obook)
        self.perp_connector.set_balance("HBOT", 500)
        self.perp_connector.set_balance("ETH", 5000)
        self.perp_connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.perp_market_info = MarketTradingPairTuple(self.perp_connector, self.trading_pair,
                                                       self.base_asset, self.quote_asset)

        self.clock.add_iterator(self.spot_connector)
        self.clock.add_iterator(self.perp_connector)

        self.spot_connector.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.spot_connector.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)
        self.perp_connector.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.perp_connector.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.strategy = SpotPerpetualArbitrageStrategy()
        self.strategy.init_params(
            spot_market_info=self.spot_market_info,
            perp_market_info=self.perp_market_info,
            order_amount=Decimal("1"),
            perp_leverage=5,
            min_divergence=Decimal("0.05"),
            min_convergence=Decimal("0.01")
        )
        self.strategy.logger().setLevel(1)
        self.strategy.logger().addHandler(self)

    def test_strategy_starts_with_existing_position(self):
        """
        Tests if the strategy can start
        """

        self.clock.add_iterator(self.strategy)
        self.perp_connector._account_positions[self.trading_pair] = Position(
            self.trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("95"),
            Decimal("1"),
            self.perp_connector.get_leverage(self.trading_pair)
        )
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertTrue(self._is_logged("INFO", "Markets are ready. Trading started."))
        self.assertTrue(self._is_logged("INFO", f"There is an existing {self.trading_pair} "
                                                f"{PositionSide.SHORT.name} position. The bot resumes "
                                                f"waiting for spreads to converge to close out the arbitrage position"))
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self.clock.backtest_til(self.start_timestamp + 2)

    def test_strategy_starts_with_existing_position_unmatched_pos_amount(self):
        """
        Tests if the strategy start then stop when there is an existing position where position amount doesn't match
        strategy order amount
        """
        self.clock.add_iterator(self.strategy)
        self.perp_connector._account_positions[self.trading_pair] = Position(
            self.trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("95"),
            Decimal("10"),
            self.perp_connector.get_leverage(self.trading_pair)
        )
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertTrue(self._is_logged("INFO", "Markets are ready. Trading started."))
        self.assertTrue(self._is_logged("INFO", f"There is an existing {self.trading_pair} "
                                                f"{PositionSide.SHORT.name} position with unmatched position amount. "
                                                f"Please manually close out the position before starting this "
                                                f"strategy."))
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self.clock.backtest_til(self.start_timestamp + 2)
        # assert the strategy stopped here
        self.assertIsNone(self.strategy.clock)

    def test_create_base_proposals(self):
        asyncio.get_event_loop().run_until_complete(self._test_create_base_proposals())

    async def _test_create_base_proposals(self):
        """
        Tests if the strategy start then stop when there is an existing position where position amount doesn't match
        strategy order amount
        """
        self.clock.add_iterator(self.strategy)
        props = await self.strategy.create_base_proposals()
        print(props)
