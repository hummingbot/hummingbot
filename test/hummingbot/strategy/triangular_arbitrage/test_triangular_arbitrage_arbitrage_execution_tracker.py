from hummingbot.core.event.events import TradeType
from hummingbot.strategy.triangular_arbitrage.order_tracking.arbitrage_execution_tracker import ArbitrageExecutionTracker
from hummingbot.strategy.triangular_arbitrage.model.opportunity import ModelOrder
from test.hummingbot.strategy.triangular_arbitrage.test_triangular_arbitrage_orderbook_preprocessor import TestOrderBookPreprocessor, TestBook


class TestArbitrageExecutionTracker(TestOrderBookPreprocessor):
    def setUp(self):
        super().setUp()
        next_trade_delay_interval: float = 15.
        execute_in_series: bool = False
        self.execution_tracker = ArbitrageExecutionTracker(
            self.arbitrage.left_edge.trading_pair,  # ETH-USDT
            self.arbitrage.cross_edge.trading_pair,  # BTC-USDT
            self.arbitrage.right_edge.trading_pair,  # ETH-BTC
            next_trade_delay_interval,
            execute_in_series,
        )

    def test_add_opportunity_cclockwise(self):
        # Raw orderbooks
        book_0 = TestBook(self.left_bids, self.left_asks)
        book_1 = TestBook(self.cross_bids, self.cross_asks)
        book_2 = TestBook(self.right_bids, self.right_asks)

        # Pre-process order book
        (left_book, cross_book, right_book) = self._preprocessor.preprocess_cclockwise(book_0, book_1, book_2, self.wallets, self.fee)
        # print(left_book)
        # print(cross_book)
        # print(right_book)

        # Create model orders using top level orders
        model_order_0 = ModelOrder(
            market_id=0,
            trading_pair=self.arbitrage.left_edge.trading_pair,
            trade_type=self.arbitrage.left_edge.trade_type,
            price=left_book[0].price,
            amount=left_book[0].amount
        )
        print(f"order_0: {model_order_0}")

        model_order_1 = ModelOrder(
            market_id=1,
            trading_pair=self.arbitrage.cross_edge.trading_pair,
            trade_type=self.arbitrage.cross_edge.trade_type,
            price=cross_book[0].price,
            amount=cross_book[0].amount
        )
        print(f"order_1: {model_order_1}")

        model_order_2 = ModelOrder(
            market_id=2,
            trading_pair=self.arbitrage.right_edge.trading_pair,
            trade_type=self.arbitrage.right_edge.trade_type,
            price=right_book[0].price,
            amount=right_book[0].amount
        )
        print(f"order_2: {model_order_2}")

        (o0, o1, o2) = self.execution_tracker.add_opportunity([model_order_0, model_order_1, model_order_2])

        print(o0)
        self.assertEqual(model_order_0.trade_type, o0.trade_type)
        if o0.trade_type == TradeType.SELL:
            self.assertTrue(model_order_0.price > o0.price)  # diff due to markup
        else:
            self.assertTrue(model_order_0.price < o0.price)  # diff due to markup

        print(o1)
        self.assertEqual(model_order_1.trade_type, o1.trade_type)
        if o1.trade_type == TradeType.SELL:
            self.assertTrue(model_order_1.price > o1.price)
        else:
            self.assertTrue(model_order_1.price < o1.price)

        print(o2)
        self.assertEqual(model_order_2.trade_type, o2.trade_type)
        if o2.trade_type == TradeType.SELL:
            self.assertTrue(model_order_2.price > o2.price)
        else:
            self.assertTrue(model_order_2.price < o2.price)

    def test_add_opportunity_clockwise(self):
        # Raw orderbooks
        book_0 = TestBook(self.right_bids, self.right_asks)
        book_1 = TestBook(self.cross_bids, self.cross_asks)
        book_2 = TestBook(self.left_bids, self.left_asks)

        # Pre-process order book
        (left_book, cross_book, right_book) = self._preprocessor.preprocess_cclockwise(book_0, book_1, book_2, self.wallets, self.fee)

        def rev_trade_f(t):
            return TradeType.BUY if t == TradeType.SELL else TradeType.SELL

        # Create model orders
        model_order_0 = ModelOrder(
            market_id=2,
            trading_pair=self.arbitrage.right_edge.trading_pair,
            trade_type=rev_trade_f(self.arbitrage.right_edge.trade_type),
            price=left_book[0].price,
            amount=left_book[0].amount
        )
        print(f"order_0: {model_order_0}")

        model_order_1 = ModelOrder(
            market_id=1,
            trading_pair=self.arbitrage.cross_edge.trading_pair,
            trade_type=rev_trade_f(self.arbitrage.cross_edge.trade_type),
            price=cross_book[0].price,
            amount=cross_book[0].amount
        )
        print(f"order_1: {model_order_1}")

        model_order_2 = ModelOrder(
            market_id=0,
            trading_pair=self.arbitrage.left_edge.trading_pair,
            trade_type=rev_trade_f(self.arbitrage.left_edge.trade_type),
            price=right_book[0].price,
            amount=right_book[0].amount
        )
        print(f"order_2: {model_order_2}")

        (o0, o1, o2) = self.execution_tracker.add_opportunity([model_order_0, model_order_1, model_order_2])

        print(o0)
        self.assertEqual(model_order_0.trade_type, o0.trade_type)
        if o0.trade_type == TradeType.SELL:
            self.assertTrue(model_order_0.price > o0.price)  # diff due to markup
        else:
            self.assertTrue(model_order_0.price < o0.price)  # diff due to markup

        print(o1)
        self.assertEqual(model_order_1.trade_type, o1.trade_type)
        if o1.trade_type == TradeType.SELL:
            self.assertTrue(model_order_1.price > o1.price)
        else:
            self.assertTrue(model_order_1.price < o1.price)

        print(o2)
        self.assertEqual(model_order_2.trade_type, o2.trade_type)
        if o2.trade_type == TradeType.SELL:
            self.assertTrue(model_order_2.price > o2.price)
        else:
            self.assertTrue(model_order_2.price < o2.price)
