from decimal import Decimal

from hummingbot.core.event.events import TradeType
from hummingbot.strategy.triangular_arbitrage.order_tracking.arbitrage_execution_tracker import ArbitrageExecutionTracker
from hummingbot.strategy.triangular_arbitrage.model.opportunity import ModelOrder
from hummingbot.strategy.triangular_arbitrage.order_tracking.order_state import OrderState
from test.hummingbot.strategy.triangular_arbitrage.test_triangular_arbitrage_orderbook_preprocessor import TestOrderBookPreprocessor, TestBook


class TestArbitrageExecutionTracker(TestOrderBookPreprocessor):
    def setUp(self):
        super().setUp()
        next_trade_delay_interval: float = 15.
        max_order_hang: float = 0.
        self.execution_tracker = ArbitrageExecutionTracker(
            self.arbitrage.left_edge.trading_pair,  # ETH-USDT
            self.arbitrage.cross_edge.trading_pair,  # BTC-USDT
            self.arbitrage.right_edge.trading_pair,  # ETH-BTC
            next_trade_delay_interval,
            max_order_hang
        )

    def test_status(self):
        self.assertFalse(self.execution_tracker.reverse)
        self.assertTrue(self.execution_tracker.ready)
        self.assertTrue(self.execution_tracker.finished)
        self.assertFalse(self.execution_tracker.recovering)
        self.assertEqual(self.execution_tracker.trade_delay, float(15.))
        self.assertFalse(self.execution_tracker.awaiting_hanging_order_completion)
        self.execution_tracker._recovering = True
        self.assertTrue(self.execution_tracker.ready)

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

    def test_order_manipulations_cc(self):
        self.test_add_opportunity_cclockwise()
        self.execution_tracker.order_placed("ETH-USDT")
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.state, OrderState.ACTIVE)
        self.execution_tracker.update_order_id("ETH-USDT", "1")
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.id, "1")
        self.execution_tracker.fill("ETH-USDT", Decimal("0.00001"))
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.state, OrderState.PARTIAL_FILL)
        order = self.execution_tracker.complete_partial_order(order)
        self.assertEqual(order.state, OrderState.PENDING_PARTIAL_TO_FULL)
        order = self.execution_tracker.all_in_order(order, Decimal('0.05'))
        self.execution_tracker.update_order_id("ETH-USDT", "1")
        self.execution_tracker.order_complete("1", "ETH-USDT")
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.state, OrderState.COMPLETE)

    # to hit the BUY routes
    def test_order_manipulations_c(self):
        self.test_add_opportunity_clockwise()
        self.execution_tracker.order_placed("ETH-USDT")
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.state, OrderState.ACTIVE)
        self.execution_tracker.update_order_id("ETH-USDT", "1")
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.id, "1")
        self.execution_tracker.fill("ETH-USDT", Decimal("0.00001"))
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.state, OrderState.PARTIAL_FILL)
        order = self.execution_tracker.complete_partial_order(order)
        self.assertEqual(order.state, OrderState.PENDING_PARTIAL_TO_FULL)
        order = self.execution_tracker.all_in_order(order, Decimal('100'))
        self.execution_tracker.update_order_id("ETH-USDT", "1")
        self.execution_tracker.order_complete("1", "ETH-USDT")
        order = self.execution_tracker._trading_pair_to_order["ETH-USDT"]
        self.assertEqual(order.state, OrderState.COMPLETE)
        order = self.execution_tracker._trading_pair_to_order["BTC-USDT"]
        reverse = self.execution_tracker.reverse_order(order)
        self.assertEqual(reverse.state, OrderState.REVERSE_PENDING)
        self.execution_tracker._trading_pair_to_order["BTC-USDT"] = reverse
        self.execution_tracker.order_placed("BTC-USDT")
        self.execution_tracker.fail("BTC-USDT")
        order = self.execution_tracker._trading_pair_to_order["BTC-USDT"]
        self.assertEqual(order.state, OrderState.REVERSE_FAILED)

    def test_order_fail_and_reversal(self):
        self.test_add_opportunity_clockwise()
        self.execution_tracker.order_placed("ETH-USDT")
        self.execution_tracker.update_order_id("ETH-BTC", "1")
        self.execution_tracker.fill("ETH-USDT", Decimal("0.00001"))
        self.execution_tracker.order_complete("1", "ETH-BTC")
        self.execution_tracker.fail("BTC-USDT")
        self.assertEqual(self.execution_tracker.reverse, True)
        self.execution_tracker.cancel("ETH-USDT")
        order = self.execution_tracker._trading_pair_to_order["ETH-BTC"]
        self.execution_tracker.order_placed("ETH-BTC")
        self.execution_tracker.update_order_id("ETH-BTC", "2")
        self.execution_tracker.order_complete("2", "ETH-BTC")
        order = self.execution_tracker._trading_pair_to_order["ETH-BTC"]
        self.assertEqual(order.state, OrderState.REVERSE_COMPLETE)
        self.execution_tracker.reset()
        self.assertEqual(self.execution_tracker.reverse, False)

    def test_get_next_actions(self):
        self.test_add_opportunity_cclockwise()
        actions = self.execution_tracker.get_next_actions()
        self.assertEqual(actions[0].action, "place")
        self.execution_tracker.order_placed("ETH-USDT")
        self.execution_tracker.order_placed("ETH-BTC")
        self.execution_tracker.order_placed("BTC-USDT")
        actions = self.execution_tracker.get_next_actions()
        self.assertEqual(actions[1].action, "cancel")
        next_trade_delay_interval: float = 15.
        max_order_hang: float = 10.
        max_order_unsent: float = 0.
        self.execution_tracker = ArbitrageExecutionTracker(
            self.arbitrage.left_edge.trading_pair,  # ETH-USDT
            self.arbitrage.cross_edge.trading_pair,  # BTC-USDT
            self.arbitrage.right_edge.trading_pair,  # ETH-BTC
            next_trade_delay_interval,
            max_order_hang,
            max_order_unsent
        )
        self.test_add_opportunity_cclockwise()
        self.execution_tracker.order_placed("ETH-USDT")
        self.execution_tracker.update_order_id("ETH-USDT", "1")
        self.execution_tracker.order_placed("ETH-BTC")
        self.execution_tracker.order_complete("1", "ETH-USDT")
        actions = self.execution_tracker.get_next_actions()
        self.assertEquals(actions, [])
        actions = self.execution_tracker.get_next_actions()
        self.assertEquals(actions[0].action, 'place')
        self.execution_tracker = ArbitrageExecutionTracker(
            self.arbitrage.left_edge.trading_pair,  # ETH-USDT
            self.arbitrage.cross_edge.trading_pair,  # BTC-USDT
            self.arbitrage.right_edge.trading_pair,  # ETH-BTC
            next_trade_delay_interval,
            max_order_hang,
            max_order_unsent
        )
        self.test_add_opportunity_cclockwise()
        self.execution_tracker.order_placed("ETH-USDT")
        self.execution_tracker.order_placed("BTC-USDT")
        actions = self.execution_tracker.get_next_actions()
        self.assertEquals(actions, [])
        self.execution_tracker = ArbitrageExecutionTracker(
            self.arbitrage.left_edge.trading_pair,  # ETH-USDT
            self.arbitrage.cross_edge.trading_pair,  # BTC-USDT
            self.arbitrage.right_edge.trading_pair,  # ETH-BTC
            next_trade_delay_interval,
            max_order_hang,
            max_order_unsent
        )
        self.test_add_opportunity_cclockwise()
        self.execution_tracker.order_placed("ETH-USDT")
        self.execution_tracker.order_placed("ETH-BTC")
        actions = self.execution_tracker.get_next_actions()
        self.assertEquals(actions, [])
        self.execution_tracker.update_order_id("ETH-USDT", "1")
        actions = self.execution_tracker.get_next_actions()
        self.assertEquals(actions[0].action, 'cancel')

    def test_set_unset_ready(self):
        self.execution_tracker.set_ready()
        self.assertEquals(self.execution_tracker._ready, True)
        self.execution_tracker.set_not_ready()
        self.assertEquals(self.execution_tracker._ready, False)
