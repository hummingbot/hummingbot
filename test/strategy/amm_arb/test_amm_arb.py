from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))
import unittest
from decimal import Decimal
import pandas as pd
import logging

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.utils.estimate_fee import default_cex_estimate
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.utils import create_arb_proposals

logging.basicConfig(level=METRICS_LOG_LEVEL)

trading_pair = "CGLD-CUSD"
base_asset = trading_pair.split("-")[0]
quote_asset = trading_pair.split("-")[1]


class AmmArbUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()

    @classmethod
    def setUpClass(cls):
        default_cex_estimate["BacktestMarket"] = [0., 0.]
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market_1: BacktestMarket = BacktestMarket()

        self.market_data_1 = MockOrderBookLoader(trading_pair, base_asset, quote_asset)
        self.market_data_1.set_balanced_order_book(10, 5, 15, 0.1, 1)

        self.market_1.add_data(self.market_data_1)

        self.market_1.set_balance(base_asset, 500)
        self.market_1.set_balance(quote_asset, 500)
        self.market_1.set_quantization_param(
            QuantizationParams(
                trading_pair, 5, 5, 5, 5
            )
        )
        self.market_info_1 = MarketTradingPairTuple(self.market_1, trading_pair, base_asset, quote_asset)

        self.market_2: BacktestMarket = BacktestMarket()
        self.market_data_2 = MockOrderBookLoader(trading_pair, base_asset, quote_asset)
        self.market_data_2.set_balanced_order_book(11, 6, 16, 0.1, 1)

        self.market_2.add_data(self.market_data_2)

        self.market_2.set_balance(base_asset, 500)
        self.market_2.set_balance(quote_asset, 500)
        self.market_2.set_quantization_param(
            QuantizationParams(
                trading_pair, 5, 5, 5, 5
            )
        )
        self.market_info_2 = MarketTradingPairTuple(self.market_2, trading_pair, base_asset, quote_asset)
        self.strategy = AmmArbStrategy(
            self.market_info_1,
            self.market_info_2,
            min_profitability=Decimal("0.01"),
            order_amount=Decimal("1"),
            slippage_buffer=Decimal("0.001"),
        )
        self.clock.add_iterator(self.market_1)
        self.clock.add_iterator(self.market_2)
        self.clock.add_iterator(self.strategy)
        self.market_order_fill_logger: EventLogger = EventLogger()
        self.market_1.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)

    def test_profitable_celo_sell_trade(self):
        order_amount = 1
        self.strategy.order_amount = order_amount
        self.clock.backtest_til(self.start_timestamp + 6)
        proposals = create_arb_proposals(self.market_info_1, self.market_info_2, order_amount)
        self.assertEqual(2, len(proposals))
