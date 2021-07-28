from datetime import datetime
import unittest
from decimal import Decimal
from mock import MagicMock, patch, PropertyMock

from hummingbot.core.event.events import MarketEvent, OrderCancelledEvent, BuyOrderCompletedEvent
from hummingbot.strategy.hanging_orders_tracker import HangingOrdersTracker, HangingOrdersAggregationType
from hummingbot.strategy.data_types import HangingOrder, OrderType
from hummingbot.core.data_type.limit_order import LimitOrder


class TestHangingOrdersTracker(unittest.TestCase):
    level = 0
    log_records = []

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.current_market_price = Decimal("100.0")
        self.strategy = self.create_mock_strategy()
        self.tracker = HangingOrdersTracker(self.strategy, hanging_orders_cancel_pct=Decimal("0.1"))

        self.tracker.logger().setLevel(1)
        self.tracker.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    @staticmethod
    def quantize_order_amount(trading_pair: str, amount: Decimal):
        return amount.quantize(Decimal("0.00001"))

    @staticmethod
    def quantize_order_price(trading_pair: str, price: Decimal):
        return price.quantize(Decimal("0.00001"))

    def create_mock_strategy(self):
        market = MagicMock()
        market.quantize_order_amount.side_effect = self.quantize_order_amount
        market.quantize_order_price.side_effect = self.quantize_order_price
        market.get_maker_order_type.return_value = OrderType.LIMIT

        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock()
        type(strategy).max_order_age = PropertyMock(return_value=1800.0)
        type(strategy).order_refresh_time = PropertyMock(return_value=45.0)
        strategy.get_price.return_value = self.current_market_price
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="BTC-USDT")

        return strategy

    def test_tracker_initialized(self):
        self.assertEqual(self.tracker.trading_pair, "BTC-USDT")
        self.assertEqual(self.tracker.original_orders, set())
        self.assertEqual(self.tracker.strategy_current_hanging_orders, set())
        self.assertEqual(self.tracker.current_created_pairs_of_orders, list())

    def test_add_remove_limit_order(self):
        order_to_add = LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1))
        self.tracker.add_order(order_to_add)
        self.assertEqual(len(self.tracker.original_orders), 1)
        order_that_doesnt_belong = LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(100),
                                              Decimal(1))
        self.tracker.remove_order(order_that_doesnt_belong)
        self.assertEqual(len(self.tracker.original_orders), 1)
        self.tracker.remove_order(order_to_add)
        self.assertEqual(len(self.tracker.original_orders), 0)
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1)))
        self.tracker.remove_all_orders()
        self.assertEqual(len(self.tracker.original_orders), 0)

    def test_renew_hanging_orders_past_max_order_age(self):
        cancelled_orders_ids = []
        strategy_active_orders = []
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234967891)
        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.return_value = "Order-1234569990000000"

        # Order just executed
        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))
        # Order executed 1900 seconds ago
        old_order = LimitOrder("Order-1234565991000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(105),
                               Decimal(1))

        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)
        self.tracker.add_order(old_order)
        strategy_active_orders.append(old_order)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        self.assertTrue(any(order.trading_pair == "BTC-USDT" and order.price == Decimal(105)
                            for order
                            in self.tracker.strategy_current_hanging_orders))

        # When calling the renew logic, the old order should start the renew process (it should be canceled)
        # but it will only stop being a current hanging order once the cancel confirmation arrives
        self.tracker.process_tick()
        self.assertTrue(old_order.client_order_id in cancelled_orders_ids)
        self.assertTrue(any(order.trading_pair == "BTC-USDT" and order.price == Decimal(105)
                            for order
                            in self.tracker.strategy_current_hanging_orders))

        # When the cancel is confirmed the order should no longer be considered a hanging order
        strategy_active_orders.remove(old_order)
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(old_order.client_order_id, old_order.client_order_id))
        self.assertTrue(self._is_logged("INFO", f"(BTC-USDT) Hanging order {old_order.client_order_id} "
                                                f"has been cancelled as part of the renew process. "
                                                f"Now the replacing order will be created."))
        self.assertFalse(any(order.order_id == old_order.client_order_id for order
                             in self.tracker.strategy_current_hanging_orders))
        self.assertTrue(any(order.order_id == "Order-1234569990000000" for order
                            in self.tracker.strategy_current_hanging_orders))

    def test_hanging_order_being_renewed_discarded_if_not_current_hanging_order_after_cancel(self):
        cancelled_orders_ids = []
        strategy_active_orders = []

        newly_created_orders_ids = ["Order-1234569990000000", "Order-1234570000000000"]

        type(self.strategy).current_timestamp = PropertyMock(return_value=1234900000)
        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.side_effect = newly_created_orders_ids

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)

        # Order just executed
        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))
        # Order executed 1900 seconds ago
        old_order = LimitOrder("Order-1234565991000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(105),
                               Decimal(1))

        self.tracker.add_order(old_order)
        strategy_active_orders.append(old_order)
        self.tracker.update_strategy_orders_with_equivalent_orders()

        # A new order should have been created.
        self.assertTrue(any(order.order_id == newly_created_orders_ids[0] for order
                            in self.tracker.strategy_current_hanging_orders))

        hanging_order = next(iter(self.tracker.strategy_current_hanging_orders))
        strategy_active_orders.append(LimitOrder(hanging_order.order_id,
                                                 hanging_order.trading_pair,
                                                 hanging_order.is_buy,
                                                 hanging_order.base_asset,
                                                 hanging_order.quote_asset,
                                                 hanging_order.price,
                                                 hanging_order.amount))

        # When calling the renew logic, the old order should start the renew process (it should be canceled)
        # but it will only stop being a current hanging order once the cancel confirmation arrives
        self.tracker.process_tick()
        self.assertTrue(newly_created_orders_ids[0] in cancelled_orders_ids)
        self.assertTrue(any(order.order_id == newly_created_orders_ids[0] for order
                            in self.tracker.strategy_current_hanging_orders))

        # Before cancellation is confirmed a new order is added to the tracker, generating a new grouped hanging order
        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)
        self.tracker.update_strategy_orders_with_equivalent_orders()

        # When the cancel is confirmed the order should no longer be considered a hanging order
        strategy_active_orders.remove(old_order)
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(old_order.client_order_id, old_order.client_order_id))
        self.assertFalse(any(order.order_id == old_order.client_order_id for order
                             in self.tracker.strategy_current_hanging_orders))
        self.assertTrue(any(order.order_id == "Order-1234569990000000" for order
                            in self.tracker.strategy_current_hanging_orders))

    def test_order_being_renewed_is_canceled_only_one_time(self):
        cancelled_orders_ids = []
        strategy_active_orders = []
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234967891)
        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.return_value = "Order-1234569990000000"

        # Order just executed
        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))
        # Order executed 1900 seconds ago
        old_order = LimitOrder("Order-1234565991000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(105),
                               Decimal(1))

        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)
        self.tracker.add_order(old_order)
        strategy_active_orders.append(old_order)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        self.assertTrue(any(order.trading_pair == "BTC-USDT" and order.price == Decimal(105)
                            for order
                            in self.tracker.strategy_current_hanging_orders))

        # When calling the renew logic, the old order should start the renew process (it should be canceled)
        # but it will only stop being a current hanging order once the cancel confirmation arrives
        self.tracker.process_tick()
        self.assertTrue(old_order.client_order_id in cancelled_orders_ids)
        # Now we suppose that a new tick happens before the cancellation confirmation arrives
        self.tracker.process_tick()
        # The cancel request should not have been sent a second time
        self.assertEqual(1, cancelled_orders_ids.count(old_order.client_order_id))

    def test_asymmetrical_volume_weighted(self):
        # Asymmetrical in distance to mid-price and amounts
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
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
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
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
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 500}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 600}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 700}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 800}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))
        with patch('time.time', return_value=current_time_mock):
            self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.assertEqual(self.tracker.strategy_current_hanging_orders,
                             {HangingOrder(order_id=None,
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
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 300}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 600}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 800}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 1200}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        with patch('time.time', return_value=current_time_mock):
            self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.assertEqual(self.tracker.strategy_current_hanging_orders,
                             {HangingOrder(order_id=None,
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
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
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
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=True,
                                       price=Decimal('96.82055'),
                                       amount=Decimal('11.00000')),
                          HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=False,
                                       price=Decimal('103.17945'),
                                       amount=Decimal('11.00000'))})

    def test_hanging_order_removed_when_cancelled(self):
        strategy_active_orders = []

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)

        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))

        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        # Now we simulate the order is cancelled
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled.value,
                                       self,
                                       OrderCancelledEvent(datetime.now().timestamp(),
                                                           new_order.client_order_id,
                                                           new_order.client_order_id))

        self.assertTrue(self._is_logged("INFO", "(BTC-USDT) Hanging order Order-1234567890000000 cancelled."))
        self.assertTrue(len(self.tracker.strategy_current_hanging_orders) == 0)
        self.assertNotIn(new_order, self.tracker.original_orders)

    def test_grouped_hanging_order_and_original_orders_removed_when_hanging_order_completed(self):
        strategy_active_orders = []
        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570020000000",
                                        "Order-1234570040000000",
                                        "Order-1234570060000000"]
        newly_created_sell_orders_ids = ["Order-1234570010000000",
                                         "Order-1234570030000000",
                                         "Order-1234570050000000",
                                         "Order-1234570070000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids
        self.strategy.sell_with_specific_market.side_effect = newly_created_sell_orders_ids

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        buy_order_2 = LimitOrder("Order-1234569980000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(105),
                                 Decimal(1))

        sell_order_1 = LimitOrder("Order-1234569970000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(110),
                                  Decimal(1))
        sell_order_2 = LimitOrder("Order-1234569990000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(115),
                                  Decimal(1))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(buy_order_2)
        strategy_active_orders.append(buy_order_2)
        self.tracker.add_order(sell_order_1)
        strategy_active_orders.append(sell_order_1)
        self.tracker.add_order(sell_order_2)
        strategy_active_orders.append(sell_order_2)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        buy_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if order.is_buy)
        sell_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if not order.is_buy)
        strategy_active_orders.remove(buy_order_1)
        strategy_active_orders.remove(buy_order_2)
        strategy_active_orders.append(buy_hanging_order)
        strategy_active_orders.append(sell_hanging_order)

        self.assertEqual(4, len(self.tracker.original_orders))
        self.assertEqual(2, len(self.tracker.strategy_current_hanging_orders))
        self.assertFalse(self.tracker.is_order_id_in_completed_hanging_orders(buy_hanging_order.order_id))
        self.assertFalse(self.tracker.is_order_id_in_completed_hanging_orders(sell_hanging_order.order_id))

        # Now we simulate the buy hanging order being fully filled
        strategy_active_orders.remove(buy_hanging_order)
        self.tracker._did_complete_buy_order(MarketEvent.BuyOrderCompleted,
                                             self,
                                             BuyOrderCompletedEvent(
                                                 timestamp=datetime.now().timestamp(),
                                                 order_id=buy_hanging_order.order_id,
                                                 base_asset="BTC",
                                                 quote_asset="USDT",
                                                 fee_asset="USDT",
                                                 base_asset_amount=buy_hanging_order.amount,
                                                 quote_asset_amount=buy_hanging_order.amount * buy_hanging_order.price,
                                                 fee_amount=Decimal(0),
                                                 order_type=OrderType.LIMIT))

        self.assertEqual(1, len(self.tracker.strategy_current_hanging_orders))
        self.assertNotIn(buy_hanging_order, self.tracker.strategy_current_hanging_orders)
        self.assertEqual(2, len(self.tracker.original_orders))
        self.assertTrue(all(not order.is_buy for order in self.tracker.original_orders))
        self.assertTrue(self.tracker.is_order_id_in_completed_hanging_orders(buy_hanging_order.order_id))
        self.assertFalse(self.tracker.is_order_id_in_completed_hanging_orders(sell_hanging_order.order_id))

        # In this moment the only hanging order in the tracker is the generated by the two sells.
        # We add a new buy hanging order to test that fully filling the sell hanging order only removes the sells

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        buy_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if order.is_buy)
        strategy_active_orders.remove(buy_order_1)
        strategy_active_orders.append(buy_hanging_order)

        self.assertEqual(3, len(self.tracker.original_orders))
        self.assertEqual(2, len(self.tracker.strategy_current_hanging_orders))
        self.assertFalse(self.tracker.is_order_id_in_completed_hanging_orders(buy_hanging_order.order_id))

        # Now we simulate the sell hanging order being fully filled
        strategy_active_orders.remove(sell_hanging_order)
        self.tracker._did_complete_sell_order(MarketEvent.BuyOrderCompleted,
                                              self,
                                              BuyOrderCompletedEvent(
                                                  timestamp=datetime.now().timestamp(),
                                                  order_id=sell_hanging_order.order_id,
                                                  base_asset="BTC",
                                                  quote_asset="USDT",
                                                  fee_asset="USDT",
                                                  base_asset_amount=sell_hanging_order.amount,
                                                  quote_asset_amount=sell_hanging_order.amount * sell_hanging_order.price,
                                                  fee_amount=Decimal(0),
                                                  order_type=OrderType.LIMIT))

        self.assertEqual(1, len(self.tracker.strategy_current_hanging_orders))
        self.assertNotIn(sell_hanging_order, self.tracker.strategy_current_hanging_orders)
        self.assertEqual(1, len(self.tracker.original_orders))
        self.assertTrue(all(order.is_buy for order in self.tracker.original_orders))
        self.assertTrue(self.tracker.is_order_id_in_completed_hanging_orders(sell_hanging_order.order_id))
        self.assertFalse(self.tracker.is_order_id_in_completed_hanging_orders(buy_hanging_order.order_id))

    def test_non_grouped_hanging_order_and_original_order_removed_when_hanging_order_completed(self):
        strategy_active_orders = []
        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570020000000",
                                        "Order-1234570040000000",
                                        "Order-1234570060000000"]
        newly_created_sell_orders_ids = ["Order-1234570010000000",
                                         "Order-1234570030000000",
                                         "Order-1234570050000000",
                                         "Order-1234570070000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids
        self.strategy.sell_with_specific_market.side_effect = newly_created_sell_orders_ids

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        sell_order_1 = LimitOrder("Order-1234569970000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(110),
                                  Decimal(1))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.NO_AGGREGATION)

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(sell_order_1)
        strategy_active_orders.append(sell_order_1)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        buy_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if order.is_buy)
        sell_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if not order.is_buy)

        self.assertEqual(buy_order_1.client_order_id, buy_hanging_order.order_id)
        self.assertEqual(sell_order_1.client_order_id, sell_hanging_order.order_id)
        self.assertEqual(2, len(self.tracker.original_orders))
        self.assertEqual(2, len(self.tracker.strategy_current_hanging_orders))

        # Now we simulate the buy hanging order being fully filled
        strategy_active_orders.remove(buy_order_1)
        self.tracker._did_complete_buy_order(MarketEvent.BuyOrderCompleted,
                                             self,
                                             BuyOrderCompletedEvent(
                                                 timestamp=datetime.now().timestamp(),
                                                 order_id=buy_order_1.client_order_id,
                                                 base_asset="BTC",
                                                 quote_asset="USDT",
                                                 fee_asset="USDT",
                                                 base_asset_amount=buy_order_1.quantity,
                                                 quote_asset_amount=buy_order_1.quantity * buy_order_1.price,
                                                 fee_amount=Decimal(0),
                                                 order_type=OrderType.LIMIT))

        self.assertEqual(1, len(self.tracker.strategy_current_hanging_orders))
        self.assertNotIn(buy_hanging_order, self.tracker.strategy_current_hanging_orders)
        self.assertEqual(1, len(self.tracker.original_orders))
        self.assertNotIn(buy_order_1, self.tracker.original_orders)
        self.assertTrue(self.tracker.is_order_id_in_completed_hanging_orders(buy_hanging_order.order_id))
        self.assertFalse(self.tracker.is_order_id_in_completed_hanging_orders(sell_hanging_order.order_id))

    def test_limit_order_added_to_grouping_tracker_is_potential_hanging_order(self):
        strategy_active_orders = []
        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570020000000",
                                        "Order-1234570040000000",
                                        "Order-1234570060000000"]
        newly_created_sell_orders_ids = ["Order-1234570010000000",
                                         "Order-1234570030000000",
                                         "Order-1234570050000000",
                                         "Order-1234570070000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids
        self.strategy.sell_with_specific_market.side_effect = newly_created_sell_orders_ids

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        buy_order_2 = LimitOrder("Order-1234569980000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(105),
                                 Decimal(1))

        sell_order_1 = LimitOrder("Order-1234569970000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(110),
                                  Decimal(1))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(buy_order_2)
        strategy_active_orders.append(buy_order_2)
        self.tracker.add_order(sell_order_1)
        strategy_active_orders.append(sell_order_1)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_1))
        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_2))
        self.assertTrue(self.tracker.is_potential_hanging_order(sell_order_1))

    def test_limit_order_added_to_non_grouping_tracker_is_potential_hanging_order(self):
        strategy_active_orders = []
        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570020000000",
                                        "Order-1234570040000000",
                                        "Order-1234570060000000"]
        newly_created_sell_orders_ids = ["Order-1234570010000000",
                                         "Order-1234570030000000",
                                         "Order-1234570050000000",
                                         "Order-1234570070000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids
        self.strategy.sell_with_specific_market.side_effect = newly_created_sell_orders_ids

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        buy_order_2 = LimitOrder("Order-1234569980000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(105),
                                 Decimal(1))

        sell_order_1 = LimitOrder("Order-1234569970000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(110),
                                  Decimal(1))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.NO_AGGREGATION)

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(buy_order_2)
        strategy_active_orders.append(buy_order_2)
        self.tracker.add_order(sell_order_1)
        strategy_active_orders.append(sell_order_1)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_1))
        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_2))
        self.assertTrue(self.tracker.is_potential_hanging_order(sell_order_1))

    def test_non_grouping_tracker_cancels_order_when_removing_far_from_price(self):
        cancelled_orders_ids = []
        strategy_active_orders = []

        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570020000000",
                                        "Order-1234570040000000",
                                        "Order-1234570060000000"]
        newly_created_sell_orders_ids = ["Order-1234570010000000",
                                         "Order-1234570030000000",
                                         "Order-1234570050000000",
                                         "Order-1234570070000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids
        self.strategy.sell_with_specific_market.side_effect = newly_created_sell_orders_ids

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.NO_AGGREGATION)

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        buy_order_2 = LimitOrder("Order-1234569980000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(120),
                                 Decimal(1))

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(buy_order_2)
        strategy_active_orders.append(buy_order_2)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        # The hanging orders are created
        hanging_order_1 = next(hanging_order for hanging_order in self.tracker.strategy_current_hanging_orders
                               if hanging_order.order_id == buy_order_1.client_order_id)
        hanging_order_2 = next(hanging_order for hanging_order in self.tracker.strategy_current_hanging_orders
                               if hanging_order.order_id == buy_order_2.client_order_id)

        # After removing orders far from price, the order 2 should be canceled but still be a hanging order
        self.tracker.remove_orders_far_from_price()
        self.assertEqual(1, len(cancelled_orders_ids))
        self.assertIn(hanging_order_2.order_id, cancelled_orders_ids)
        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_2))
        # We simulate a new request to remove orders far from price before the cancellation confirmation arrives
        # The order should not be cancelled again. Both the order and the hanging order should still be present
        self.tracker.remove_orders_far_from_price()
        self.assertEqual(1, cancelled_orders_ids.count(buy_order_2.client_order_id))
        self.assertIn(hanging_order_2.order_id, cancelled_orders_ids)
        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_2))

        # We emulate the reception of the cancellation confirmation. After that the hanging order should not be present
        # in the tracker, and the original order should not be considered a potential hanging order.
        strategy_active_orders.remove(buy_order_2)
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(buy_order_2.client_order_id, buy_order_2.client_order_id))

        self.assertNotIn(hanging_order_2, self.tracker.strategy_current_hanging_orders)
        self.assertFalse(self.tracker.is_potential_hanging_order(buy_order_2))
        self.assertIn(hanging_order_1, self.tracker.strategy_current_hanging_orders)
        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_1))

    def test_grouping_tracker_removes_original_order_when_removing_far_from_price(self):
        cancelled_orders_ids = []
        strategy_active_orders = []

        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570020000000",
                                        "Order-1234570040000000",
                                        "Order-1234570060000000"]
        newly_created_sell_orders_ids = ["Order-1234570010000000",
                                         "Order-1234570030000000",
                                         "Order-1234570050000000",
                                         "Order-1234570070000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids
        self.strategy.sell_with_specific_market.side_effect = newly_created_sell_orders_ids

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        buy_order_2 = LimitOrder("Order-1234569980000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(120),
                                 Decimal(1))

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(buy_order_2)
        strategy_active_orders.append(buy_order_2)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        # The hanging orders are created
        grouped_hanging_order = next(iter(self.tracker.strategy_current_hanging_orders))
        strategy_active_orders.append(LimitOrder(grouped_hanging_order.order_id,
                                                 grouped_hanging_order.trading_pair,
                                                 grouped_hanging_order.is_buy,
                                                 "BTC",
                                                 "USDT",
                                                 grouped_hanging_order.price,
                                                 grouped_hanging_order.amount))

        # After removing orders far from price, no order is cancelled, but buy_order_2 should no longer be considered
        # a potential hanging order
        self.tracker.remove_orders_far_from_price()
        self.assertEqual(0, len(cancelled_orders_ids))

        self.assertFalse(self.tracker.is_potential_hanging_order(buy_order_2))
        self.assertTrue(self.tracker.is_potential_hanging_order(buy_order_1))

        # The hanging order will still be the same, until it is recreated
        self.assertIn(grouped_hanging_order, self.tracker.strategy_current_hanging_orders)

        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(1, len(cancelled_orders_ids))
        self.assertIn(grouped_hanging_order.order_id, cancelled_orders_ids)

        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(grouped_hanging_order.order_id,
                                                           grouped_hanging_order.order_id))
        new_grouped_hanging_order = next(iter(self.tracker.strategy_current_hanging_orders))
        self.assertNotEqual(grouped_hanging_order, new_grouped_hanging_order)
        self.assertNotIn(grouped_hanging_order, self.tracker.strategy_current_hanging_orders)
