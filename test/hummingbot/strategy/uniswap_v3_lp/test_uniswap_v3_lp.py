"""
Unit tests for hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp
"""

from decimal import Decimal
import pandas as pd
from typing import Dict, List
import unittest.mock

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader


class UniswapV3LpStrategyTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    market_infos: Dict[str, MarketTradingPairTuple] = {}

    @staticmethod
    def create_market(trading_pairs: List[str], mid_price, balances: Dict[str, int]) -> (BacktestMarket, Dict[str, MarketTradingPairTuple]):
        """
        Create a BacktestMarket and marketinfo dictionary to be used by the liquidity mining strategy
        """
        market: BacktestMarket = BacktestMarket()
        market_infos: Dict[str, MarketTradingPairTuple] = {}

        for trading_pair in trading_pairs:
            base_asset = trading_pair.split("-")[0]
            quote_asset = trading_pair.split("-")[1]

            book_data: MockOrderBookLoader = MockOrderBookLoader(trading_pair, base_asset, quote_asset)
            book_data.set_balanced_order_book(mid_price=mid_price,
                                              min_price=1,
                                              max_price=200,
                                              price_step_size=1,
                                              volume_step_size=10)
            market.add_data(book_data)
            market.set_quantization_param(QuantizationParams(trading_pair, 6, 6, 6, 6))
            market_infos[trading_pair] = MarketTradingPairTuple(market, trading_pair, base_asset, quote_asset)

        for asset, value in balances.items():
            market.set_balance(asset, value)

        return market, market_infos

    def setUp(self) -> None:
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)

        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 1

        trading_pairs = list(map(lambda quote_asset: "ETH-" + quote_asset, ["USDT", "BTC"]))
        market, market_infos = self.create_market(trading_pairs, self.mid_price, {"USDT": 5000, "ETH": 500, "BTC": 100})
        self.market = market
        self.market_infos = market_infos

        self.clock.add_iterator(self.market)
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.default_strategy = UniswapV3LpStrategy(
            self.market_infos[trading_pairs[0]],
            True,
            Decimal("144"),
            Decimal("2"),
            "MEDIUM",
            Decimal('0.01'),
            Decimal('0.01'),
            Decimal('1'),
            Decimal('1'),
            Decimal('5'),
        )

    def test_generate_proposal_with_volatility(self):
        """
        Test that the generate proposal function works correctly
        """

        self.default_strategy._last_price = Decimal("100")
        buy_lower, buy_upper = self.default_strategy.generate_proposal(True)
        self.assertEqual(buy_upper, Decimal("100"))
        self.assertEqual(buy_lower, Decimal("99"))
        sell_lower, sell_upper = self.default_strategy.generate_proposal(False)
        self.assertEqual(sell_upper, Decimal("101"))
        self.assertEqual(sell_lower, Decimal("100"))

    def test_generate_proposal_without_volatility(self):
        """
        Test that the generate proposal function works correctly
        """

        self.default_strategy._use_volatility = False
        self.default_strategy._last_price = Decimal("100")
        buy_lower, buy_upper = self.default_strategy.generate_proposal(True)
        self.assertEqual(buy_upper, Decimal("100"))
        self.assertEqual(buy_lower, Decimal("99"))
        sell_lower, sell_upper = self.default_strategy.generate_proposal(False)
        self.assertEqual(sell_upper, Decimal("101"))
        self.assertEqual(sell_lower, Decimal("100"))
