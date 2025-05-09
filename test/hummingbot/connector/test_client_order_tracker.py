import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable, Dict
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    AddedToCostTradeFee,
    BuyOrderCompletedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)


class MockExchange(ExchangeBase):

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return dict()


class ClientOrderTrackerUnitTest(unittest.TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.trade_fee_percent = Decimal("0.001")

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.connector = MockExchange(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.connector._set_current_timestamp(1640000000.0)
        self.tracker = ClientOrderTracker(connector=self.connector)

        self.tracker.logger().setLevel(1)
        self.tracker.logger().addHandler(self)

        self._initialize_event_loggers()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.connector.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_start_tracking_order(self):
        self.assertEqual(0, len(self.tracker.active_orders))

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )

        self.tracker.start_tracking_order(order)

        self.assertEqual(1, len(self.tracker.active_orders))

    def test_stop_tracking_order(self):
        self.assertEqual(0, len(self.tracker.active_orders))

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)
        self.assertEqual(1, len(self.tracker.active_orders))

        self.tracker.stop_tracking_order(order.client_order_id)

        self.assertEqual(0, len(self.tracker.active_orders))
        self.assertEqual(1, len(self.tracker.cached_orders))

    def test_cached_order_max_cache_size(self):
        for i in range(ClientOrderTracker.MAX_CACHE_SIZE + 1):
            order: InFlightOrder = InFlightOrder(
                client_order_id=f"someClientOrderId_{i}",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                creation_timestamp=1640001112.0,
                price=Decimal("1.0"),
            )
            self.tracker._cached_orders[order.client_order_id] = order

        self.assertEqual(ClientOrderTracker.MAX_CACHE_SIZE, len(self.tracker.cached_orders))

        # First entry gets removed when the no. of cached order exceeds MAX_CACHE_SIZE
        self.assertNotIn("someClientOrderId_0", self.tracker._cached_orders)

    def test_cached_order_ttl_not_exceeded(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker._cached_orders[order.client_order_id] = order

        self.assertIn(order.client_order_id, self.tracker._cached_orders)

    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.CACHED_ORDER_TTL", 0.1)
    def test_cached_order_ttl_exceeded(self):
        tracker = ClientOrderTracker(self.connector)
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        tracker._cached_orders[order.client_order_id] = order

        self.ev_loop.run_until_complete(asyncio.sleep(0.2))

        self.assertNotIn(order.client_order_id, tracker.cached_orders)

    def test_fetch_tracked_order_not_found(self):
        self.assertIsNone(self.tracker.fetch_tracked_order("someNonExistantOrderId"))

    def test_fetch_tracked_order(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)
        self.assertEqual(1, len(self.tracker.active_orders))

        fetched_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)

        self.assertTrue(fetched_order == order)

    def test_fetch_cached_order_not_found(self):
        self.assertIsNone(self.tracker.fetch_cached_order("someNonExistantOrderId"))

    def test_fetch_cached_order(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker._cached_orders[order.client_order_id] = order
        self.assertEqual(1, len(self.tracker.cached_orders))

        fetched_order: InFlightOrder = self.tracker.fetch_cached_order(order.client_order_id)

        self.assertTrue(fetched_order == order)

    def test_fetch_order_by_client_order_id(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)
        self.assertEqual(1, len(self.tracker.active_orders))

        fetched_order: InFlightOrder = self.tracker.fetch_order(order.client_order_id)

        self.assertTrue(fetched_order == order)

    def test_fetch_order_by_exchange_order_id(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)
        self.assertEqual(1, len(self.tracker.active_orders))

        fetched_order: InFlightOrder = self.tracker.fetch_order(exchange_order_id=order.exchange_order_id)

        self.assertTrue(fetched_order == order)

    def test_fetch_order_does_not_match_orders_with_undefined_exchange_id(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)
        self.assertEqual(1, len(self.tracker.active_orders))

        fetched_order = self.tracker.fetch_order("invalid_order_id")

        self.assertIsNone(fetched_order)

    def test_process_order_update_invalid_order_update(self):

        order_creation_update: OrderUpdate = OrderUpdate(
            # client_order_id="someClientOrderId",  # client_order_id intentionally omitted
            # exchange_order_id="someExchangeOrderId",  # client_order_id intentionally omitted
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(update_future)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "OrderUpdate does not contain any client_order_id or exchange_order_id",
            )
        )

    def test_process_order_update_order_not_found(self):

        order_creation_update: OrderUpdate = OrderUpdate(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(update_future)

        self.assertTrue(
            self._is_logged(
                "DEBUG",
                f"Order is not/no longer being tracked ({order_creation_update})",
            )
        )

    def test_process_order_update_trigger_order_creation_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)

        order_creation_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(update_future)

        updated_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)

        # Check order update has been successfully applied
        self.assertEqual(updated_order.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertTrue(updated_order.exchange_order_id_update_event.is_set())
        self.assertEqual(updated_order.current_state, order_creation_update.new_state)
        self.assertTrue(updated_order.is_open)

        # Check that Logger has logged the correct log
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name} {order.trade_type.name} order {order.client_order_id} for "
                f"{order.amount} {order.trading_pair} at {order.price}.",
            )
        )

        # Check that Buy/SellOrderCreatedEvent has been triggered.
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        event_logged = self.buy_order_created_logger.event_log[0]
        self.assertEqual(event_logged.amount, order.amount)
        self.assertEqual(event_logged.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertEqual(event_logged.order_id, order.client_order_id)
        self.assertEqual(event_logged.price, order.price)
        self.assertEqual(event_logged.trading_pair, order.trading_pair)
        self.assertEqual(event_logged.type, order.order_type)

    def test_process_order_update_trigger_order_creation_event_without_client_order_id(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",  # exchange_order_id is provided when initialized. See AscendEx.
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)

        order_creation_update: OrderUpdate = OrderUpdate(
            # client_order_id=order.client_order_id,  # client_order_id purposefully ommited
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(update_future)

        updated_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)

        # Check order update has been successfully applied
        self.assertEqual(updated_order.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertTrue(updated_order.exchange_order_id_update_event.is_set())
        self.assertEqual(updated_order.current_state, order_creation_update.new_state)
        self.assertTrue(updated_order.is_open)

        # Check that Logger has logged the correct log
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name} {order.trade_type.name} order {order.client_order_id} for "
                f"{order.amount} {order.trading_pair} at {order.price}.",
            )
        )

        # Check that Buy/SellOrderCreatedEvent has been triggered.
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        event_logged = self.buy_order_created_logger.event_log[0]

        self.assertEqual(event_logged.amount, order.amount)
        self.assertEqual(event_logged.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertEqual(event_logged.order_id, order.client_order_id)
        self.assertEqual(event_logged.price, order.price)
        self.assertEqual(event_logged.trading_pair, order.trading_pair)
        self.assertEqual(event_logged.type, order.order_type)

    def test_process_order_update_with_pending_status_does_not_trigger_order_creation_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)

        order_creation_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=order.current_state,
        )

        update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(update_future)

        updated_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)

        # Check order update has been successfully applied
        self.assertEqual(updated_order.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertTrue(updated_order.exchange_order_id_update_event.is_set())
        self.assertTrue(updated_order.is_pending_create)

        self.assertFalse(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name} {order.trade_type.name} order {order.client_order_id} for "
                f"{order.amount} {order.trading_pair}.",
            )
        )

        # Check that Buy/SellOrderCreatedEvent has not been triggered.
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))

    def test_process_order_update_trigger_order_cancelled_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )

        self.tracker.start_tracking_order(order)

        order_cancelled_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.CANCELED,
        )

        update_future = self.tracker.process_order_update(order_cancelled_update)
        self.async_run_with_timeout(update_future)

        self.assertTrue(self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}."))
        self.assertEqual(0, len(self.tracker.active_orders))
        self.assertEqual(1, len(self.tracker.cached_orders))
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        event_triggered = self.order_cancelled_logger.event_log[0]
        self.assertIsInstance(event_triggered, OrderCancelledEvent)
        self.assertEqual(event_triggered.exchange_order_id, order.exchange_order_id)
        self.assertEqual(event_triggered.order_id, order.client_order_id)

    def test_process_order_update_trigger_order_failure_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )

        self.tracker.start_tracking_order(order)

        order_failure_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.FAILED,
        )

        update_future = self.tracker.process_order_update(order_failure_update)
        self.async_run_with_timeout(update_future)

        self.assertTrue(
            self._is_logged("INFO", f"Order {order.client_order_id} has failed. Order Update: {order_failure_update}")
        )
        self.assertEqual(0, len(self.tracker.active_orders))
        self.assertEqual(1, len(self.tracker.cached_orders))
        self.assertEqual(1, len(self.order_failure_logger.event_log))

        event_triggered = self.order_failure_logger.event_log[0]
        self.assertIsInstance(event_triggered, MarketOrderFailureEvent)
        self.assertEqual(event_triggered.order_id, order.client_order_id)
        self.assertEqual(event_triggered.order_type, order.order_type)

    def test_process_order_update_trigger_completed_event_and_not_fill_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        initial_order_filled_amount = order.amount / Decimal("2.0")
        order_update_1: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.PARTIALLY_FILLED,
        )

        update_future = self.tracker.process_order_update(order_update_1)
        self.async_run_with_timeout(update_future)

        # Check order update has been successfully applied
        updated_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)
        self.assertEqual(updated_order.exchange_order_id, order_update_1.exchange_order_id)
        self.assertTrue(updated_order.exchange_order_id_update_event.is_set())
        self.assertEqual(updated_order.current_state, order_update_1.new_state)
        self.assertTrue(updated_order.is_open)

        subsequent_order_filled_amount = order.amount - initial_order_filled_amount
        order_update_2: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=2,
            new_state=OrderState.FILLED,
        )

        # Force order to not wait for filled events from TradeUpdate objects
        order.completely_filled_event.set()
        update_future = self.tracker.process_order_update(order_update_2)
        self.async_run_with_timeout(update_future)

        # Check order is not longer being actively tracked
        self.assertIsNone(self.tracker.fetch_tracked_order(order.client_order_id))

        cached_order: InFlightOrder = self.tracker.fetch_cached_order(order.client_order_id)
        self.assertEqual(cached_order.current_state, order_update_2.new_state)
        self.assertTrue(cached_order.is_done)

        # Check that Logger has logged the appropriate logs
        self.assertFalse(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{initial_order_filled_amount}/{order.amount} {order.base_asset} has been filled.",
            )
        )
        self.assertFalse(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{initial_order_filled_amount + subsequent_order_filled_amount}/{order.amount} {order.base_asset} "
                f"has been filled.",
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO", f"{order.trade_type.name.upper()} order {order.client_order_id} completely filled."
            )
        )

        self.assertEqual(0, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_process_trade_update_trigger_filled_event_flat_fee(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        trade_filled_price: Decimal = Decimal("0.5")
        trade_filled_amount: Decimal = order.amount / Decimal("2.0")
        fee_paid: Decimal = self.trade_fee_percent * trade_filled_amount
        trade_update: TradeUpdate = TradeUpdate(
            trade_id=1,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_price=trade_filled_price,
            fill_base_amount=trade_filled_amount,
            fill_quote_amount=trade_filled_price * trade_filled_amount,
            fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote_asset, amount=fee_paid)]),
            fill_timestamp=1,
        )

        self.tracker.process_trade_update(trade_update)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{trade_filled_amount}/{order.amount} {order.base_asset} has been filled at {trade_filled_price} {order.quote_asset}.",
            )
        )

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        order_filled_event: OrderFilledEvent = self.order_filled_logger.event_log[0]

        self.assertEqual(order_filled_event.order_id, order.client_order_id)
        self.assertEqual(order_filled_event.price, trade_update.fill_price)
        self.assertEqual(order_filled_event.amount, trade_update.fill_base_amount)
        self.assertEqual(
            order_filled_event.trade_fee, AddedToCostTradeFee(flat_fees=[TokenAmount(self.quote_asset, fee_paid)])
        )

    def test_process_trade_update_does_not_trigger_filled_event_update_status_when_completely_filled(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        fee_paid: Decimal = self.trade_fee_percent * order.amount
        trade_update: TradeUpdate = TradeUpdate(
            trade_id=1,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_price=order.price,
            fill_base_amount=order.amount,
            fill_quote_amount=order.price * order.amount,
            fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote_asset, amount=fee_paid)]),
            fill_timestamp=1,
        )

        self.tracker.process_trade_update(trade_update)

        fetched_order: InFlightOrder = self.tracker.fetch_order(order.client_order_id)
        self.assertTrue(fetched_order.is_filled)
        self.assertIn(fetched_order.client_order_id, self.tracker.active_orders)
        self.assertNotIn(fetched_order.client_order_id, self.tracker.cached_orders)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{order.amount}/{order.amount} {order.base_asset} has been filled at {order.price} {order.quote_asset}.",
            )
        )

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        order_filled_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertIsNotNone(order_filled_event)

        self.assertEqual(order_filled_event.order_id, order.client_order_id)
        self.assertEqual(order_filled_event.price, trade_update.fill_price)
        self.assertEqual(order_filled_event.amount, trade_update.fill_base_amount)
        self.assertEqual(
            order_filled_event.trade_fee, AddedToCostTradeFee(flat_fees=[TokenAmount(self.quote_asset, fee_paid)])
        )

    def test_updating_order_states_with_both_process_order_update_and_process_trade_update(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)

        order_creation_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(update_future)

        open_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)

        # Check order_creation_update has been successfully applied
        self.assertEqual(open_order.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertTrue(open_order.exchange_order_id_update_event.is_set())
        self.assertEqual(open_order.current_state, order_creation_update.new_state)
        self.assertTrue(open_order.is_open)
        self.assertEqual(0, len(open_order.order_fills))

        trade_filled_price: Decimal = order.price
        trade_filled_amount: Decimal = order.amount
        fee_paid: Decimal = self.trade_fee_percent * trade_filled_amount
        trade_update: TradeUpdate = TradeUpdate(
            trade_id=1,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_price=trade_filled_price,
            fill_base_amount=trade_filled_amount,
            fill_quote_amount=trade_filled_price * trade_filled_amount,
            fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote_asset, amount=fee_paid)]),
            fill_timestamp=2,
        )

        self.tracker.process_trade_update(trade_update)
        self.assertEqual(1, len(self.tracker.active_orders))
        self.assertEqual(0, len(self.tracker.cached_orders))

    def test_process_order_not_found_invalid_order(self):
        self.assertEqual(0, len(self.tracker.active_orders))

        unknown_order_id = "UNKNOWN_ORDER_ID"
        self.async_run_with_timeout(self.tracker.process_order_not_found(unknown_order_id))

        self._is_logged("DEBUG", f"Order is not/no longer being tracked ({unknown_order_id})")

    def test_process_order_not_found_does_not_exceed_limit(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertIn(order.client_order_id, self.tracker.active_orders)
        self.assertIn(order.client_order_id, self.tracker._order_not_found_records)
        self.assertEqual(1, self.tracker._order_not_found_records[order.client_order_id])

    def test_process_order_not_found_exceeded_limit(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))
        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertNotIn(order.client_order_id, self.tracker.active_orders)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.223,
            price=Decimal("1.0"),
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.223,
            price=Decimal("1.0"),
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.tracker.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.tracker.active_orders)
        self.assertNotIn("OID2", self.tracker.all_orders)
        self.assertNotIn("OID3", self.tracker.all_orders)
        self.assertNotIn("OID4", self.tracker.all_orders)

    def test_update_to_close_order_is_not_processed_until_order_completelly_filled(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        )
        self.tracker.start_tracking_order(order)

        order_creation_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id="1",
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=order.trading_pair,
            fill_price=Decimal("1100"),
            fill_base_amount=order.amount,
            fill_quote_amount=order.amount * Decimal("1100"),
            fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("10"))]),
            fill_timestamp=10,
        )

        order_completion_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=2,
            new_state=OrderState.FILLED,
        )

        # We invert the orders update processing on purpose, to force the test scenario without using sleeps
        self.connector._set_current_timestamp(1640001100)
        completion_update_future = self.tracker.process_order_update(order_completion_update)

        self.connector._set_current_timestamp(1640001105)
        creation_update_future = self.tracker.process_order_update(order_creation_update)
        self.async_run_with_timeout(creation_update_future)

        order: InFlightOrder = self.tracker.fetch_order(client_order_id=order.client_order_id)

        # Check order_creation_update has been successfully applied
        self.assertFalse(order.is_done)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.completely_filled_event.is_set())

        fill_timetamp = 1640001115
        self.connector._set_current_timestamp(fill_timetamp)
        self.tracker.process_trade_update(trade_update)
        self.assertTrue(order.completely_filled_event.is_set())

        self.connector._set_current_timestamp(1640001120)
        self.async_run_with_timeout(completion_update_future)

        self.assertTrue(order.is_filled)
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(fill_timetamp, fill_event.timestamp)

        complete_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertGreaterEqual(complete_event.timestamp, 1640001120)

    def test_access_lost_orders(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertEqual(0, len(self.tracker.lost_orders))

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertEqual(1, len(self.tracker.lost_orders))
        self.assertIn(order.client_order_id, self.tracker.lost_orders)

    def test_lost_orders_returned_in_all_fillable_orders(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))
        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertIn(order.client_order_id, self.tracker.all_fillable_orders)
        self.assertNotIn(order.client_order_id, self.tracker.cached_orders)

    def test_lost_orders_returned_in_all_updatable_orders(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))
        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertIn(order.client_order_id, self.tracker.all_updatable_orders)
        self.assertNotIn(order.client_order_id, self.tracker.cached_orders)

    def test_lost_order_removed_when_fully_filled(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))
        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertIn(order.client_order_id, self.tracker.lost_orders)

        order_completion_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=2,
            new_state=OrderState.FILLED,
        )

        self.async_run_with_timeout(self.tracker.process_order_update(order_update=order_completion_update))

        self.assertTrue(order.is_failure)
        self.assertNotIn(order.client_order_id, self.tracker.lost_orders)

    def test_lost_order_removed_when_canceled(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))
        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertIn(order.client_order_id, self.tracker.lost_orders)

        order_completion_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=2,
            new_state=OrderState.CANCELED,
        )

        self.async_run_with_timeout(self.tracker.process_order_update(order_update=order_completion_update))

        self.assertTrue(order.is_failure)
        self.assertNotIn(order.client_order_id, self.tracker.lost_orders)

    def test_lost_order_not_removed_when_updated_with_non_final_states(self):
        self.tracker = ClientOrderTracker(connector=self.connector, lost_order_count_limit=1)

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.0,
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))
        self.async_run_with_timeout(self.tracker.process_order_not_found(order.client_order_id))

        self.assertIn(order.client_order_id, self.tracker.lost_orders)

        update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=2,
            new_state=OrderState.OPEN,
        )

        self.async_run_with_timeout(self.tracker.process_order_update(order_update=update))

        self.assertTrue(order.is_failure)
        self.assertIn(order.client_order_id, self.tracker.lost_orders)

        update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=3,
            new_state=OrderState.PARTIALLY_FILLED,
        )

        self.async_run_with_timeout(self.tracker.process_order_update(order_update=update))

        self.assertTrue(order.is_failure)
        self.assertIn(order.client_order_id, self.tracker.lost_orders)

        update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=3,
            new_state=OrderState.PENDING_CANCEL,
        )

        self.async_run_with_timeout(self.tracker.process_order_update(order_update=update))

        self.assertTrue(order.is_failure)
        self.assertIn(order.client_order_id, self.tracker.lost_orders)

    def test_setting_lost_order_count_limit(self):
        self.tracker.lost_order_count_limit = 1

        self.assertEqual(1, self.tracker.lost_order_count_limit)

        self.tracker.lost_order_count_limit = 2

        self.assertEqual(2, self.tracker.lost_order_count_limit)
