import asyncio
import unittest
from decimal import Decimal
from typing import List, Optional
from unittest.mock import patch

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import (
    AddedToCostTradeFee,
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    TradeType
)


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

        self.connector = ConnectorBase()
        self.connector._set_current_timestamp(1640000000.0)
        self.tracker = ClientOrderTracker(connector=self.connector)

        self.tracker.logger().setLevel(1)
        self.tracker.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def test_start_tracking_order(self):
        self.assertEqual(0, len(self.tracker.active_orders))

        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
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
            price=Decimal("1.0"),
        )
        self.tracker.start_tracking_order(order)
        self.assertEqual(1, len(self.tracker.active_orders))

        fetched_order: InFlightOrder = self.tracker.fetch_order(exchange_order_id=order.exchange_order_id)

        self.assertTrue(fetched_order == order)

    def test_process_order_update_invalid_order_update(self):

        order_creation_update: OrderUpdate = OrderUpdate(
            # client_order_id="someClientOrderId",  # client_order_id intentionally omitted
            # exchange_order_id="someExchangeOrderId",  # client_order_id intentionally omitted
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.OPEN,
        )

        self.tracker.process_order_update(order_creation_update)

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

        self.tracker.process_order_update(order_creation_update)

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

        self.tracker.process_order_update(order_creation_update)

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
                f"{order.amount} {order.trading_pair}.",
            )
        )

        # Check that Buy/SellOrderCreatedEvent has been triggered.
        self.assertEqual(1, len(self.connector.event_logs))
        event_logged = self.connector.event_logs[0]

        self.assertIsInstance(event_logged, BuyOrderCreatedEvent)
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

        self.tracker.process_order_update(order_creation_update)

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
                f"{order.amount} {order.trading_pair}.",
            )
        )

        # Check that Buy/SellOrderCreatedEvent has been triggered.
        self.assertEqual(1, len(self.connector.event_logs))
        event_logged = self.connector.event_logs[0]

        self.assertIsInstance(event_logged, BuyOrderCreatedEvent)
        self.assertEqual(event_logged.amount, order.amount)
        self.assertEqual(event_logged.exchange_order_id, order_creation_update.exchange_order_id)
        self.assertEqual(event_logged.order_id, order.client_order_id)
        self.assertEqual(event_logged.price, order.price)
        self.assertEqual(event_logged.trading_pair, order.trading_pair)
        self.assertEqual(event_logged.type, order.order_type)

    def test_process_order_update_trigger_order_cancelled_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )

        self.tracker.start_tracking_order(order)

        order_cancelled_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.CANCELLED,
        )

        self.tracker.process_order_update(order_cancelled_update)

        self.assertTrue(self._is_logged("INFO", f"Successfully cancelled order {order.client_order_id}."))
        self.assertEqual(0, len(self.tracker.active_orders))
        self.assertEqual(1, len(self.tracker.cached_orders))
        self.assertEqual(1, len(self.connector.event_logs))

        event_triggered = self.connector.event_logs[0]
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

        self.tracker.process_order_update(order_failure_update)

        self.assertTrue(
            self._is_logged("INFO", f"Order {order.client_order_id} has failed. Order Update: {order_failure_update}")
        )
        self.assertEqual(0, len(self.tracker.active_orders))
        self.assertEqual(1, len(self.tracker.cached_orders))
        self.assertEqual(1, len(self.connector.event_logs))

        event_triggered = self.connector.event_logs[0]
        self.assertIsInstance(event_triggered, MarketOrderFailureEvent)
        self.assertEqual(event_triggered.order_id, order.client_order_id)
        self.assertEqual(event_triggered.order_type, order.order_type)

    def test_process_order_update_trigger_filled_and_completed_event(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        initial_order_filled_amount = order.amount / Decimal("2.0")
        initial_fee_paid = self.trade_fee_percent * initial_order_filled_amount
        order_fill_update_1: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=1,
            new_state=OrderState.PARTIALLY_FILLED,
            trade_id=1,
            fill_price=order.price,
            executed_amount_base=initial_order_filled_amount,
            executed_amount_quote=order.price * initial_order_filled_amount,
            fee_asset=self.base_asset,
            cumulative_fee_paid=initial_fee_paid,
        )

        self.tracker.process_order_update(order_fill_update_1)

        # Check order update has been successfully applied
        updated_order: InFlightOrder = self.tracker.fetch_tracked_order(order.client_order_id)
        self.assertEqual(updated_order.exchange_order_id, order_fill_update_1.exchange_order_id)
        self.assertTrue(updated_order.exchange_order_id_update_event.is_set())
        self.assertEqual(updated_order.current_state, order_fill_update_1.new_state)
        self.assertTrue(updated_order.is_open)

        subsequent_order_filled_amount = order.amount - initial_order_filled_amount
        subsequent_fee_paid = self.trade_fee_percent * subsequent_order_filled_amount
        order_fill_update_2: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            update_timestamp=2,
            new_state=OrderState.FILLED,
            trade_id=2,
            fill_price=order.price,
            executed_amount_base=initial_order_filled_amount + subsequent_order_filled_amount,
            executed_amount_quote=order.price * order.amount,
            fee_asset=self.base_asset,
            cumulative_fee_paid=initial_fee_paid + subsequent_fee_paid,
        )

        self.tracker.process_order_update(order_fill_update_2)

        # Check order is not longer being actively tracked
        self.assertIsNone(self.tracker.fetch_tracked_order(order.client_order_id))

        cached_order: InFlightOrder = self.tracker.fetch_cached_order(order.client_order_id)
        self.assertEqual(cached_order.current_state, order_fill_update_2.new_state)
        self.assertTrue(cached_order.is_done)

        # Check that Logger has logged the appropriate logs
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{order_fill_update_1.executed_amount_base}/{order.amount} {order.base_asset} has been filled.",
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{order_fill_update_2.executed_amount_base}/{order.amount} {order.base_asset} has been filled.",
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO", f"{order.trade_type.name.upper()} order {order.client_order_id} completely filled."
            )
        )

        self.assertEqual(3, len(self.connector.event_logs))
        order_fill_events: List[OrderFilledEvent] = [
            event for event in self.connector.event_logs if isinstance(event, OrderFilledEvent)
        ]
        order_completed_events: List[BuyOrderCompletedEvent] = [
            event for event in self.connector.event_logs if isinstance(event, BuyOrderCompletedEvent)
        ]

        self.assertEqual(2, len(order_fill_events))
        self.assertEqual(1, len(order_completed_events))

    def test_process_trade_update_trigger_filled_event_flat_fee(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
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
            fee_asset=self.base_asset,
            fee_paid=fee_paid,
            fill_timestamp=1,
        )

        self.tracker.process_trade_update(trade_update)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{trade_filled_amount}/{order.amount} {order.base_asset} has been filled.",
            )
        )

        self.assertEqual(1, len(self.connector.event_logs))
        order_filled_event: OrderFilledEvent = self.connector.event_logs[0]

        self.assertEqual(order_filled_event.order_id, order.client_order_id)
        self.assertEqual(order_filled_event.price, trade_update.fill_price)
        self.assertEqual(order_filled_event.amount, trade_update.fill_base_amount)
        self.assertEqual(
            order_filled_event.trade_fee, AddedToCostTradeFee(flat_fees=[TokenAmount(self.base_asset, fee_paid)])
        )

    def test_process_trade_update_trigger_filled_event_trade_fee_percent(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
            trade_fee_percent=self.trade_fee_percent,
        )
        self.tracker.start_tracking_order(order)

        order_filled_price: Decimal = Decimal("0.5")
        order_filled_amount: Decimal = order.amount / Decimal("2.0")
        trade_update: TradeUpdate = TradeUpdate(
            trade_id=1,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_price=order_filled_price,
            fill_base_amount=order_filled_amount,
            fill_quote_amount=order_filled_price * order_filled_amount,
            fee_asset=self.base_asset,
            fill_timestamp=1,
        )

        self.tracker.process_trade_update(trade_update)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{order_filled_amount}/{order.amount} {order.base_asset} has been filled.",
            )
        )

        self.assertEqual(1, len(self.connector.event_logs))
        order_filled_event: OrderFilledEvent = self.connector.event_logs[0]

        self.assertEqual(order_filled_event.order_id, order.client_order_id)
        self.assertEqual(order_filled_event.price, trade_update.fill_price)
        self.assertEqual(order_filled_event.amount, trade_update.fill_base_amount)
        self.assertEqual(order_filled_event.trade_fee, AddedToCostTradeFee(self.trade_fee_percent))

    def test_process_trade_update_trigger_filled_event_update_status_when_completely_filled(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
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
            fee_asset=self.base_asset,
            fee_paid=fee_paid,
            fill_timestamp=1,
        )

        self.tracker.process_trade_update(trade_update)

        fetched_order: InFlightOrder = self.tracker.fetch_order(order.client_order_id)
        self.assertTrue(fetched_order.is_filled)
        self.assertNotIn(fetched_order.client_order_id, self.tracker.active_orders)
        self.assertIn(fetched_order.client_order_id, self.tracker.cached_orders)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to "
                f"{order.amount}/{order.amount} {order.base_asset} has been filled.",
            )
        )

        self.assertEqual(2, len(self.connector.event_logs))

        order_filled_event: Optional[OrderFilledEvent] = None
        order_completed_event: Optional[BuyOrderCompletedEvent] = None
        for event in self.connector.event_logs:
            if isinstance(event, OrderFilledEvent):
                order_filled_event = event
            if isinstance(event, BuyOrderCompletedEvent):
                order_completed_event = event

        self.assertIsNotNone(order_filled_event)
        self.assertIsNotNone(order_completed_event)

        self.assertEqual(order_filled_event.order_id, order.client_order_id)
        self.assertEqual(order_filled_event.price, trade_update.fill_price)
        self.assertEqual(order_filled_event.amount, trade_update.fill_base_amount)
        self.assertEqual(
            order_filled_event.trade_fee, AddedToCostTradeFee(flat_fees=[TokenAmount(self.base_asset, fee_paid)])
        )

        self.assertEqual(order_completed_event.order_id, order.client_order_id)
        self.assertEqual(order_completed_event.exchange_order_id, order.exchange_order_id)
        self.assertEqual(order_completed_event.base_asset_amount, order.amount)
        self.assertEqual(
            order_completed_event.quote_asset_amount, trade_update.fill_price * trade_update.fill_base_amount
        )
        self.assertEqual(order_completed_event.fee_amount, trade_update.fee_paid)

    def test_updating_order_states_with_both_process_order_update_and_process_trade_update(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
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

        self.tracker.process_order_update(order_creation_update)

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
            fee_asset=self.base_asset,
            fee_paid=fee_paid,
            fill_timestamp=2,
        )

        self.tracker.process_trade_update(trade_update)
        self.assertEqual(0, len(self.tracker.active_orders))
        self.assertEqual(1, len(self.tracker.cached_orders))

    def test_process_order_not_found_invalid_order(self):
        self.assertEqual(0, len(self.tracker.active_orders))

        unknown_order_id = "UNKNOWN_ORDER_ID"
        self.tracker.process_order_not_found(unknown_order_id)

        self._is_logged("DEBUG", f"Order is not/no longer being tracked ({unknown_order_id})")

    def test_process_order_not_found_does_not_exceed_limit(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.tracker.process_order_not_found(order.client_order_id)

        self.assertIn(order.client_order_id, self.tracker.active_orders)
        self.assertIn(order.client_order_id, self.tracker._order_not_found_records)
        self.assertEqual(1, self.tracker._order_not_found_records[order.client_order_id])

    def test_process_order_not_found_exceeded_limit(self):
        order: InFlightOrder = InFlightOrder(
            client_order_id="someClientOrderId",
            exchange_order_id="someExchangeOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.OPEN,
        )
        self.tracker.start_tracking_order(order)

        self.tracker._order_not_found_records[order.client_order_id] = 3
        self.tracker.process_order_not_found(order.client_order_id)

        self.assertNotIn(order.client_order_id, self.tracker.active_orders)
