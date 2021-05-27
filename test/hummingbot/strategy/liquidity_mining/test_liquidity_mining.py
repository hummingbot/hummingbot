from decimal import Decimal
import pandas as pd
from typing import Dict, List, Optional
import unittest.mock

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderBookTradeEvent, TradeType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.liquidity_mining.liquidity_mining import LiquidityMiningStrategy

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.event.events import TradeFee


class LiquidityMiningTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    base_asset = "ETH"
    quote_assets = ["USDT", "BTC"]
    trading_pairs = list(map(lambda quote_asset: "ETH-" + quote_asset, quote_assets))
    market_infos: Dict[str, MarketTradingPairTuple] = {}

    def setUp(self) -> None:
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: BacktestMarket = BacktestMarket()

        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30

        # liquidity_mining supports multiple pairs with a single base asset
        for trading_pair in self.trading_pairs:
            base_asset = trading_pair.split("-")[0]
            quote_asset = trading_pair.split("-")[1]

            book_data: MockOrderBookLoader = MockOrderBookLoader(trading_pair, base_asset, quote_asset)
            book_data.set_balanced_order_book(mid_price=self.mid_price,
                                              min_price=1,
                                              max_price=200,
                                              price_step_size=1,
                                              volume_step_size=10)
            self.market.add_data(book_data)
            self.market.set_quantization_param(QuantizationParams(trading_pair, 6, 6, 6, 6))
            self.market_infos[trading_pair] = MarketTradingPairTuple(self.market, trading_pair, base_asset, quote_asset)

        self.market.set_balance("USDT", 500)
        self.market.set_balance("ETH", 500)
        self.market.set_balance("BTC", 100)

        self.clock.add_iterator(self.market)
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.default_strategy = LiquidityMiningStrategy(
            exchange=self.market,
            market_infos=self.market_infos,
            token="ETH",
            order_amount=Decimal(10),
            spread=Decimal(0.5),
            inventory_skew_enabled=False,
            target_base_pct=Decimal(0.2),
            order_refresh_time=60,
            order_refresh_tolerance_pct=Decimal(0.1)
            # inventory_range_multiplier: Decimal = Decimal("1"),
            # volatility_interval: int = 60 * 5,
            # avg_volatility_period: int = 10,
            # volatility_to_spread_multiplier: Decimal = Decimal("1"),
            # max_spread: Decimal = Decimal("-1"),
            # max_order_age: float = 60. * 60.,
            # status_report_interval: float = 900,
            # hb_app_notification: bool = False
        )

    def tearDown(self) -> None:
        pass

    def simulate_maker_market_trade(
            self, is_buy: bool, quantity: Decimal, price: Decimal, trading_pair: str, market: Optional[BacktestMarket] = None,
    ):
        """
        simulate making a trade, broadcasts a trade event
        """
        if market is None:
            market = self.market
        order_book = market.get_order_book(trading_pair)
        trade_event = OrderBookTradeEvent(
            trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    @staticmethod
    def has_limit_order_type(limit_orders: List[LimitOrder], trading_pair: str, is_buy: bool) -> bool:
        for limit_order in limit_orders:
            if limit_order.trading_pair == trading_pair and limit_order.is_buy == is_buy:
                return True
        return False

    @unittest.mock.patch('hummingbot.strategy.liquidity_mining.liquidity_mining.estimate_fee')
    def test_trade(self, estimate_fee_mock):
        estimate_fee_mock.return_value = TradeFee(percent=0, flat_fees=[('ETH', Decimal(0.00005))])

        # initiate
        self.clock.add_iterator(self.default_strategy)
        self.clock.backtest_til(self.start_timestamp)

        # assert that there are no active trades on initialization and before clock has moved forward
        self.assertEqual(0, len(self.default_strategy.active_orders))

        # advance by one tick, the strategy will initiate two orders per pair
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(4, len(self.default_strategy.active_orders))

        # Simulate buy order fill
        self.simulate_maker_market_trade(False, 55, 1, "ETH-USDT")
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size * 2)
        self.assertEqual(3, len(self.default_strategy.active_orders))
        # self.clock.backtest_til(self.start_timestamp + self.clock_tick_size * 3 + 1)
        # self.assertEqual(4, len(self.default_strategy.active_orders))

        # Siomulate sell
        self.simulate_maker_market_trade(True, 250, 10, "ETH-USDT")
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size * 2)
        self.assertEqual(3, len(self.default_strategy.active_orders))

        # self.assertFalse(self.has_limit_order_type(self.default_strategy.active_orders, "ETH-USDT", False))
        # self.assertEqual(3, len(self.default_strategy.active_orders))
        # self.assertEqual(has_limit_order_type(), len(self.default_strategy.active_orders))
        # self.simulate_maker_market_trade(True, 1, 1, "ETH-USDT")
        # self.default_strategy.tick(self.start_timestamp + self.clock_tick_size + 1)
        # print(self.default_strategy.active_orders)
        # self.assertEqual(2, len(self.default_strategy.active_orders))
        # print(self.default_strategy.active_orders)

    def test_multiple_markets(self):
        """
        Liquidity Mining supports one base asset but multiple quote assets
        """
        pass

    def test_order_refresh_time(self):
        """
        Assert that orders are refreshed within the expected time
        """
        pass

    def test_tolerance_level(self):
        """
        Test tolerance level
        """
        pass

    def test_budget_allocation(self):
        """
        budget allocation is different from pmm, depends on the token base and it gives a budget between multiple pairs
        (backtestmarket may not support this yet), this comes from hummingsim
        """
        pass

    def test_simulate_maker_market_trade(self):
        """
        simulate a purchase/asset, simulate_maker_market_trade
        """
        pass

    def test_inventory_skew(self):
        """
        inventory skew is same as pmm
        """

    def test_volatility(self):
        """
        volatility calculation, how it adjusts the bid/ask spread, collects the mid price data, calculates volatility (how far it moved from lowest to highest)
        it adjusts the spread (volatility_to_spread_multiplier)
        """
        pass
