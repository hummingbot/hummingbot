import logging
import asyncio

from collections import defaultdict
from decimal import Decimal
from typing import Callable, Dict, Optional
from cachetools import TTLCache

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeType,
)
from hummingbot.logger.logger import HummingbotLogger

cot_logger = None


class ClientOrderTracker:

    MAX_CACHE_SIZE = 1000
    CACHED_ORDER_TTL = 30.0  # seconds
    MARKET_EVENTS = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFilled,
        MarketEvent.OrderFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
    ]
    ORDER_NOT_FOUND_COUNT_LIMIT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global cot_logger
        if cot_logger is None:
            cot_logger = logging.getLogger(__name__)
        return cot_logger

    def __init__(self, connector: ConnectorBase) -> None:
        """
        Provides utilities for connectors to update in-flight orders and also handle order errors.
        Also it maintains cached orders to allow for additional updates to occur after the original order is determined to
        no longer be active.
        An error constitutes, but is not limited to, the following:
        (1) Order not found on exchange.
        (2) Cannot retrieve exchange_order_id of an order
        (3) Error thrown by exchange when fetching order status
        """
        self._connector: ConnectorBase = connector
        self._in_flight_orders: Dict[str, InFlightOrder] = {}
        self._cached_orders: TTLCache = TTLCache(maxsize=self.MAX_CACHE_SIZE, ttl=self.CACHED_ORDER_TTL)

        self._order_tracking_task: Optional[asyncio.Task] = None
        self._last_poll_timestamp: int = -1
        self._order_not_found_records: Dict[str, int] = defaultdict(lambda: 0)

    @property
    def active_orders(self) -> Dict[str, InFlightOrder]:
        """
        Returns orders that are actively tracked
        """
        return self._in_flight_orders

    @property
    def cached_orders(self) -> Dict[str, InFlightOrder]:
        """
        Returns orders that are no longer actively tracked.
        """
        return {client_order_id: order for client_order_id, order in self._cached_orders.items()}

    @property
    def all_orders(self) -> Dict[str, InFlightOrder]:
        """
        Returns both active and cached order.
        """
        return {**self.active_orders, **self.cached_orders}

    @property
    def current_timestamp(self) -> int:
        """
        Returns current timestamp in milliseconds.
        """
        return int(self._connector.current_timestamp * 1e3)

    def start_tracking_order(self, order: InFlightOrder):
        self._in_flight_orders[order.client_order_id] = order

    def stop_tracking_order(self, client_order_id: str):
        if client_order_id in self._in_flight_orders:
            self._cached_orders[client_order_id] = self._in_flight_orders[client_order_id]
            del self._in_flight_orders[client_order_id]

    def fetch_tracked_order(self, client_order_id: str) -> Optional[InFlightOrder]:
        return self._in_flight_orders.get(client_order_id, None)

    def fetch_cached_order(self, client_order_id: str) -> Optional[InFlightOrder]:
        return self._cached_orders.get(client_order_id, None)

    def fetch_order(
        self, client_order_id: Optional[str] = None, exchange_order_id: Optional[str] = None
    ) -> Optional[InFlightOrder]:
        if client_order_id in self.all_orders:
            return self.all_orders[client_order_id]

        for order in self.all_orders.values():
            if order.exchange_order_id == exchange_order_id:
                return order
        return None

    def _trigger_created_event(self, order: InFlightOrder):
        event_tag = MarketEvent.BuyOrderCreated if order.trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
        event_class: Callable = BuyOrderCreatedEvent if order.trade_type is TradeType.BUY else SellOrderCreatedEvent
        self._connector.trigger_event(
            event_tag,
            event_class(
                self.current_timestamp,
                order.order_type,
                order.trading_pair,
                order.amount,
                order.price,
                order.client_order_id,
                exchange_order_id=order.exchange_order_id,
            ),
        )

    def _trigger_cancelled_event(self, order: InFlightOrder):
        self._connector.trigger_event(
            MarketEvent.OrderCancelled,
            OrderCancelledEvent(
                timestamp=self.current_timestamp,
                order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
            ),
        )

    def _trigger_filled_event(self, order: InFlightOrder):
        self._connector.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                timestamp=self.current_timestamp,
                order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                trade_type=order.trade_type,
                order_type=order.order_type,
                price=order.last_filled_price,
                amount=order.last_filled_amount,
                trade_fee=order.latest_trade_fee,
                exchange_trade_id=str(order.last_trade_id),
                leverage=int(order.leverage),
                position=order.position.name,
            ),
        )

    def _trigger_completed_event(self, order: InFlightOrder):
        event_tag = (
            MarketEvent.BuyOrderCompleted if order.trade_type is TradeType.BUY else MarketEvent.SellOrderCompleted
        )
        event_class = BuyOrderCompletedEvent if order.trade_type is TradeType.BUY else SellOrderCompletedEvent
        self._connector.trigger_event(
            event_tag,
            event_class(
                self.current_timestamp,
                order.client_order_id,
                order.base_asset,
                order.quote_asset,
                order.fee_asset,
                order.executed_amount_base,
                order.executed_amount_quote,
                order.cumulative_fee_paid,
                order.order_type,
                order.exchange_order_id,
            ),
        )

    def _trigger_failure_event(self, order: InFlightOrder):
        self._connector.trigger_event(
            MarketEvent.OrderFailure,
            MarketOrderFailureEvent(
                timestamp=self.current_timestamp,
                order_id=order.client_order_id,
                order_type=order.order_type,
            ),
        )

    def _trigger_order_creation(self, tracked_order: InFlightOrder, previous_state: OrderState, new_state: OrderState):
        if previous_state == OrderState.PENDING_CREATE and new_state == OrderState.OPEN:
            self.logger().info(
                f"Created {tracked_order.order_type.name.upper()} {tracked_order.trade_type.name.upper()} order "
                f"{tracked_order.client_order_id} for {tracked_order.amount} {tracked_order.trading_pair}."
            )
            self._trigger_created_event(tracked_order)

    def _trigger_order_fills(self, tracked_order: InFlightOrder, prev_executed_amount_base: Decimal):
        if prev_executed_amount_base < tracked_order.executed_amount_base:
            self.logger().info(
                f"The {tracked_order.trade_type.name.upper()} order {tracked_order.client_order_id} "
                f"amounting to {tracked_order.executed_amount_base}/{tracked_order.amount} "
                f"{tracked_order.base_asset} has been filled."
            )
            self._trigger_filled_event(tracked_order)

    def _trigger_order_completion(self, tracked_order: InFlightOrder, order_update: Optional[OrderUpdate] = None):
        if tracked_order.is_open:
            return

        if tracked_order.is_cancelled:
            self._trigger_cancelled_event(tracked_order)
            self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")

        elif tracked_order.is_filled:
            self._trigger_completed_event(tracked_order)
            self.logger().info(
                f"{tracked_order.trade_type.name.upper()} order {tracked_order.client_order_id} completely filled."
            )

        elif tracked_order.is_failure:
            self._trigger_failure_event(tracked_order)
            self.logger().info(f"Order {tracked_order.client_order_id} has failed. Order Update: {order_update}")

        self.stop_tracking_order(tracked_order.client_order_id)

    def process_order_update(self, order_update: OrderUpdate):
        if not order_update.client_order_id and not order_update.exchange_order_id:
            self.logger().error("OrderUpdate does not contain any client_order_id or exchange_order_id", exc_info=True)
            return

        tracked_order: Optional[InFlightOrder] = self.fetch_order(
            order_update.client_order_id, order_update.exchange_order_id
        )

        if tracked_order:
            previous_state: OrderState = tracked_order.current_state
            previous_executed_amount_base: Decimal = tracked_order.executed_amount_base

            updated: bool = tracked_order.update_with_order_update(order_update)
            if updated:
                self._trigger_order_creation(tracked_order, previous_state, order_update.new_state)
                self._trigger_order_fills(tracked_order, previous_executed_amount_base)
                self._trigger_order_completion(tracked_order, order_update)

        else:
            self.logger().debug(f"Order is not/no longer being tracked ({order_update})")

    def process_trade_update(self, trade_update: TradeUpdate):
        client_order_id: str = trade_update.client_order_id

        tracked_order: Optional[InFlightOrder] = self.fetch_order(client_order_id)

        if tracked_order:
            previous_executed_amount_base: Decimal = tracked_order.executed_amount_base

            updated: bool = tracked_order.update_with_trade_update(trade_update)
            if updated:
                self._trigger_order_fills(tracked_order, previous_executed_amount_base)
                self._trigger_order_completion(tracked_order, trade_update)

    def process_order_not_found(self, client_order_id: str):
        """
        Increments and checks if the order specified has exceeded the ORDER_NOT_FOUND_COUNT_LIMIT.
        A failed event is triggered if necessary.

        :param client_order_id: Client order id of an order.
        :type client_order_id: str
        """
        # Only concerned with active orders.
        tracked_order: Optional[InFlightOrder] = self.fetch_tracked_order(client_order_id=client_order_id)

        if tracked_order is None:
            self.logger().debug(f"Order is not/no longer being tracked ({client_order_id})")

        self._order_not_found_records[client_order_id] += 1

        if self._order_not_found_records[client_order_id] > self.ORDER_NOT_FOUND_COUNT_LIMIT:
            if not tracked_order.is_done:
                tracked_order.current_state = OrderState.FAILED
                self.stop_tracking_order(client_order_id=client_order_id)
                self._trigger_failure_event(tracked_order)
