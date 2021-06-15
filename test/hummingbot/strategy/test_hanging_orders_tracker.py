import unittest
from decimal import Decimal
from mock import MagicMock, patch
from hummingbot.strategy.hanging_orders_tracker import HangingOrdersTracker, HangingOrdersAggregationType
from hummingbot.strategy.data_types import HangingOrder, OrderType
from hummingbot.core.data_type.limit_order import LimitOrder


class MarketMock(MagicMock):
    PRECISION = Decimal("0.00001")

    def quantize_order_amount(self, trading_pair: str, amount: Decimal):
        return amount.quantize(MarketMock.PRECISION)

    def quantize_order_price(self, trading_pair: str, price: Decimal):
        return price.quantize(MarketMock.PRECISION)

    def get_maker_order_type(self):
        return OrderType.LIMIT


class StrategyMock(MagicMock):
    @property
    def max_order_age(self) -> float:
        return 1800.0

    @property
    def order_refresh_time(self) -> float:
        return 45.0

    def get_price(self) -> Decimal:
        return Decimal("100.0")

    @property
    def market_info(self):
        market_info_mock = MagicMock()
        market_info_mock.market = MarketMock()
        return market_info_mock

    @property
    def trading_pair(self):
        return "BTC-USDT"


class TestHangingOrdersTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = StrategyMock()
        self.tracker = HangingOrdersTracker(self.strategy, hanging_orders_cancel_pct=Decimal("0.1"))

    def test_tracker_initialized(self):
        self.assertEqual(self.tracker.trading_pair, "BTC-USDT")
        self.assertEqual(self.tracker.orders_to_be_created, set())
        self.assertEqual(self.tracker.original_orders, set())
        self.assertEqual(self.tracker.strategy_current_hanging_orders, set())
        self.assertEqual(self.tracker.current_created_pairs_of_orders, list())

    def test_add_remove_limit_order(self):
        order_to_add = LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1))
        self.tracker.add_order(order_to_add)
        self.assertEqual(len(self.tracker.original_orders), 1)
        order_that_doesnt_belong = LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1))
        self.tracker.remove_order(order_that_doesnt_belong)
        self.assertEqual(len(self.tracker.original_orders), 1)
        self.tracker.remove_order(order_to_add)
        self.assertEqual(len(self.tracker.original_orders), 0)
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1)))
        self.tracker.remove_all_orders()
        self.assertEqual(len(self.tracker.original_orders), 0)

    def test_update_orders_to_be_created(self):
        order_to_add = LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1))
        self.tracker.add_order(order_to_add)
        self.tracker.set_aggregation_method(HangingOrdersAggregationType.NO_AGGREGATION)
        self.tracker.update_strategy_orders_with_equivalent_orders()

        self.assertEqual(self.tracker.orders_to_be_created,
                         {HangingOrder("Order-number-1", "BTC-USDT", True, Decimal(100), Decimal(1))})

    def test_remove_orders_far_from_price(self):
        # hanging_orders_cancel_pct = 10% so will add one closer and one further
        # Current price = 100.0
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", False, "BTC", "USDT", Decimal(120), Decimal(1)))
        self.assertEqual(len(self.tracker.original_orders), 2)
        self.tracker.remove_orders_far_from_price()
        self.assertEqual(len(self.tracker.original_orders), 1)

    def test_renew_hanging_orders_past_max_order_age(self):
        current_time_mock = 1234567891
        # Order just executed
        self.tracker.add_order(LimitOrder("Order-1234567890000000",
                                          "BTC-USDT",
                                          True,
                                          "BTC",
                                          "USDT",
                                          Decimal(101),
                                          Decimal(1)))
        # Order executed 1900 seconds ago
        self.tracker.add_order(LimitOrder("Order-1234565991000000",
                                          "BTC-USDT",
                                          True,
                                          "BTC",
                                          "USDT",
                                          Decimal(105),
                                          Decimal(1)))

        with patch('time.time', return_value=current_time_mock):
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.tracker.execute_orders_to_be_created()
            self.tracker.renew_hanging_orders_past_max_order_age()
            self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(None,
                                                                              "BTC-USDT",
                                                                              True,
                                                                              Decimal(105),
                                                                              Decimal(1))})

    def test_asymmetrical_volume_weighted(self):
        # Asymmetrical in distance to mid-price and amounts
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=True,
                                                                          price=Decimal('97.66667'),
                                                                          amount=Decimal('3.00000')),
                                                             HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=False,
                                                                          price=Decimal('107.36364'),
                                                                          amount=Decimal('11.00000'))})

    def test_symmetrical_volume_weighted(self):
        # Symmetrical in distance to mid-price and amounts
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=True,
                                                                          price=Decimal('95.36364'),
                                                                          amount=Decimal('11.00000')),
                                                             HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=False,
                                                                          price=Decimal('104.63636'),
                                                                          amount=Decimal('11.00000'))})

    def test_asymmetrical_volume_age_weighted(self):
        current_time_mock = 1234567891
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-500}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-600}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-700}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-800}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))
        with patch('time.time', return_value=current_time_mock):
            self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(order_id=None,
                                                                              trading_pair='BTC-USDT',
                                                                              is_buy=True,
                                                                              price=Decimal('95.31641'),
                                                                              amount=Decimal('9.00000')),
                                                                 HangingOrder(order_id=None,
                                                                              trading_pair='BTC-USDT',
                                                                              is_buy=False,
                                                                              price=Decimal('109.00000'),
                                                                              amount=Decimal('5.00000'))})

    def test_symmetrical_volume_age_weighted(self):
        # Symmetrical in distance to mid-price and amounts, BUT different ages
        current_time_mock = 1234567891
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-300}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-600}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-800}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock-1200}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        with patch('time.time', return_value=current_time_mock):
            self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(order_id=None,
                                                                              trading_pair='BTC-USDT',
                                                                              is_buy=True,
                                                                              price=Decimal('95.69098'),
                                                                              amount=Decimal('11.00000')),
                                                                 HangingOrder(order_id=None,
                                                                              trading_pair='BTC-USDT',
                                                                              is_buy=False,
                                                                              price=Decimal('104.20177'),
                                                                              amount=Decimal('11.00000'))})

    def test_asymmetrical_volume_distance_weighted(self):
        # Asymmetrical in distance to mid-price and amounts, BUT with distance affecting the weight exponentially
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_DISTANCE_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=False,
                                                                          price=Decimal('107.14511'),
                                                                          amount=Decimal('11.00000')),
                                                             HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=True,
                                                                          price=Decimal('97.99590'),
                                                                          amount=Decimal('3.00000'))})

    def test_symmetrical_volume_distance_weighted(self):
        # Symmetrical in distance to mid-price and amounts, BUT with distance affecting the weight exponentially
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_DISTANCE_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.orders_to_be_created, {HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=True,
                                                                          price=Decimal('96.82055'),
                                                                          amount=Decimal('11.00000')),
                                                             HangingOrder(order_id=None,
                                                                          trading_pair='BTC-USDT',
                                                                          is_buy=False,
                                                                          price=Decimal('103.17945'),
                                                                          amount=Decimal('11.00000'))})
