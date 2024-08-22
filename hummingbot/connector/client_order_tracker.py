import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from itertools import chain
from typing import TYPE_CHECKING, Callable, Dict, Optional

from cachetools import TTLCache

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.connector_base import ConnectorBase

cot_logger = None


class ClientOrderTracker:

    MAX_CACHE_SIZE = 1000
    CACHED_ORDER_TTL = 30.0  # seconds
    TRADE_FILLS_WAIT_TIMEOUT = 5  # seconds

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global cot_logger
        if cot_logger is None:
            cot_logger = logging.getLogger(__name__)
        return cot_logger

    def __init__(self, connector: "ConnectorBase", lost_order_count_limit: int = 3) -> None:
        """
        Provides utilities for connectors to update in-flight orders and also handle order errors.
        Also it maintains cached orders to allow for additional updates to occur after the original order
        is determined to no longer be active.
        An error constitutes, but is not limited to, the following:
        (1) Order not found on exchange.
        (2) Cannot retrieve exchange_order_id of an order
        (3) Error thrown by exchange when fetching order status
        """
        self._connector: ConnectorBase = connector
        self._lost_order_count_limit = lost_order_count_limit
        self._in_flight_orders: Dict[str, InFlightOrder] = {}
        self._cached_orders: TTLCache = TTLCache(maxsize=self.MAX_CACHE_SIZE, ttl=self.CACHED_ORDER_TTL)
        self._lost_orders: Dict[str, InFlightOrder] = {}

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
    def all_fillable_orders(self) -> Dict[str, InFlightOrder]:
        """
        Returns all orders that could still be impacted by trades: active orders, cached orders and lost orders
        """
        return {**self.active_orders, **self.cached_orders, **self.lost_orders}

    @property
    def all_fillable_orders_by_exchange_order_id(self) -> Dict[str, InFlightOrder]:
        """
        Same as `all_fillable_orders`, but the orders are mapped by exchange order ID.
        """
        orders_map = {
            order.exchange_order_id: order
            for order in chain(self.active_orders.values(), self.cached_orders.values(), self.lost_orders.values())
        }
        return orders_map

    @property
    def all_updatable_orders(self) -> Dict[str, InFlightOrder]:
        """
        Returns all orders that could receive status updates
        """
        return {**self.active_orders, **self.lost_orders}

    @property
    def all_updatable_orders_by_exchange_order_id(self) -> Dict[str, InFlightOrder]:
        """
        Same as `all_updatable_orders`, but the orders are mapped by exchange order ID.
        """
        orders_map = {
            order.exchange_order_id: order for order in chain(self.active_orders.values(), self.lost_orders.values())
        }
        return orders_map

    @property
    def current_timestamp(self) -> int:
        """
        Returns current timestamp in seconds.
        """
        return self._connector.current_timestamp

    @property
    def lost_orders(self) -> Dict[str, InFlightOrder]:
        """
        Returns a dictionary of all orders marked as failed after not being found more times than the configured limit
        """
        return {client_order_id: order for client_order_id, order in self._lost_orders.items()}

    @property
    def lost_order_count_limit(self) -> int:
        return self._lost_order_count_limit

    @lost_order_count_limit.setter
    def lost_order_count_limit(self, value: int):
        self._lost_order_count_limit = value

    def start_tracking_order(self, order: InFlightOrder):
        self._in_flight_orders[order.client_order_id] = order

    def stop_tracking_order(self, client_order_id: str):
        if client_order_id in self._in_flight_orders:
            self._cached_orders[client_order_id] = self._in_flight_orders[client_order_id]
            del self._in_flight_orders[client_order_id]
            if client_order_id in self._order_not_found_records:
                del self._order_not_found_records[client_order_id]

    def restore_tracking_states(self, tracking_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states.
        :param tracking_states: a dictionary associating order ids with the serialized order (JSON format).
        """
        for serialized_order in tracking_states.values():
            order = self._restore_order_from_json(serialized_order=serialized_order)
            if order.is_open:
                self.start_tracking_order(order)
            elif order.is_failure:
                # If the order is marked as failed but is still in the tracking states, it was a lost order
                self._lost_orders[order.client_order_id] = order

    def fetch_tracked_order(self, client_order_id: str) -> Optional[InFlightOrder]:
        return self._in_flight_orders.get(client_order_id, None)

    def fetch_cached_order(self, client_order_id: str) -> Optional[InFlightOrder]:
        return self._cached_orders.get(client_order_id, None)

    def fetch_order(
        self, client_order_id: Optional[str] = None, exchange_order_id: Optional[str] = None
    ) -> Optional[InFlightOrder]:
        found_order = None

        if client_order_id in self.all_orders:
            found_order = self.all_orders[client_order_id]
        elif exchange_order_id is not None:
            found_order = next(
                (order for order in self.all_orders.values() if order.exchange_order_id == exchange_order_id), None
            )

        return found_order

    def fetch_lost_order(
        self, client_order_id: Optional[str] = None, exchange_order_id: Optional[str] = None
    ) -> Optional[InFlightOrder]:
        found_order = None

        if client_order_id in self._lost_orders:
            found_order = self._lost_orders[client_order_id]
        elif exchange_order_id is not None:
            found_order = next(
                (order for order in self._lost_orders.values() if order.exchange_order_id == exchange_order_id),
                None)

        return found_order

    def process_order_update(self, order_update: OrderUpdate):
        return safe_ensure_future(self._process_order_update(order_update))

    def process_trade_update(self, trade_update: TradeUpdate):
        client_order_id: str = trade_update.client_order_id

        tracked_order: Optional[InFlightOrder] = self.all_fillable_orders.get(client_order_id)

        if tracked_order:
            previous_executed_amount_base: Decimal = tracked_order.executed_amount_base

            updated: bool = tracked_order.update_with_trade_update(trade_update)
            if updated:
                self._trigger_order_fills(
                    tracked_order=tracked_order,
                    prev_executed_amount_base=previous_executed_amount_base,
                    fill_amount=trade_update.fill_base_amount,
                    fill_price=trade_update.fill_price,
                    fill_fee=trade_update.fee,
                    trade_id=trade_update.trade_id,
                    exchange_order_id=trade_update.exchange_order_id,
                )

    async def process_order_not_found(self, client_order_id: str):
        """
        Increments and checks if the order specified has exceeded the order_not_found_count_limit.
        A failed event is triggered if necessary.

        :param client_order_id: Client order id of an order.
        :type client_order_id: str
        """
        # Only concerned with active orders.
        tracked_order: Optional[InFlightOrder] = self.fetch_tracked_order(client_order_id=client_order_id)

        if tracked_order is not None:
            self._order_not_found_records[client_order_id] += 1
            if self._order_not_found_records[client_order_id] > self._lost_order_count_limit:
                # Only mark the order as failed if it has not been marked as done already asynchronously
                if tracked_order.current_state not in [OrderState.CANCELED, OrderState.FILLED, OrderState.FAILED]:
                    self.logger().warning(
                        f"The order {client_order_id}({tracked_order.exchange_order_id}) will be "
                        f"considered lost. Please check its status in the exchange."
                    )
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=client_order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.FAILED,
                    )
                    await self._process_order_update(order_update)
                    del self._cached_orders[client_order_id]
                    self._lost_orders[tracked_order.client_order_id] = tracked_order
        else:
            lost_order = self._lost_orders.get(client_order_id)
            if lost_order is not None:
                self.logger().info(
                    f"The lost order {client_order_id}({lost_order.exchange_order_id}) was not found "
                    f"and will be removed"
                )
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=client_order_id,
                    trading_pair=lost_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FAILED,
                )
                await self._process_order_update(order_update)
            else:
                self.logger().debug(f"Order is not/no longer being tracked ({client_order_id})")

    async def _process_order_update(self, order_update: OrderUpdate):
        if not order_update.client_order_id and not order_update.exchange_order_id:
            self.logger().error("OrderUpdate does not contain any client_order_id or exchange_order_id", exc_info=True)
            return

        tracked_order: Optional[InFlightOrder] = self.fetch_order(
            order_update.client_order_id, order_update.exchange_order_id
        )

        if tracked_order:
            if order_update.new_state == OrderState.FILLED and not tracked_order.is_done:
                try:
                    await asyncio.wait_for(
                        tracked_order.wait_until_completely_filled(), timeout=self.TRADE_FILLS_WAIT_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    self.logger().warning(
                        f"The order fill updates did not arrive on time for {tracked_order.client_order_id}. "
                        f"The complete update will be processed with incomplete information."
                    )

            previous_state: OrderState = tracked_order.current_state

            updated: bool = tracked_order.update_with_order_update(order_update)
            if updated:
                self._trigger_order_creation(tracked_order, previous_state, order_update.new_state)
                self._trigger_order_completion(tracked_order, order_update)
        else:
            lost_order = self.fetch_lost_order(
                client_order_id=order_update.client_order_id, exchange_order_id=order_update.exchange_order_id
            )
            if lost_order:
                if order_update.new_state in [OrderState.CANCELED, OrderState.FILLED, OrderState.FAILED]:
                    # If the order officially reaches a final state after being lost it should be removed from the lost list
                    del self._lost_orders[lost_order.client_order_id]
            else:
                self.logger().debug(f"Order is not/no longer being tracked ({order_update})")

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
                order.creation_timestamp,
                exchange_order_id=order.exchange_order_id,
                leverage=order.leverage,
                position=order.position.value,
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

    def _trigger_filled_event(
        self,
        order: InFlightOrder,
        fill_amount: Decimal,
        fill_price: Decimal,
        fill_fee: TradeFeeBase,
        trade_id: str,
        exchange_order_id: str,
    ):
        self._connector.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                timestamp=self.current_timestamp,
                order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                trade_type=order.trade_type,
                order_type=order.order_type,
                price=fill_price,
                amount=fill_amount,
                trade_fee=fill_fee,
                exchange_trade_id=trade_id,
                leverage=int(order.leverage),
                position=order.position.value,
                exchange_order_id=exchange_order_id,
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
                order.executed_amount_base,
                order.executed_amount_quote,
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
        if (previous_state == OrderState.PENDING_CREATE and
                previous_state != new_state and
                new_state not in [OrderState.CANCELED, OrderState.FAILED, OrderState.PENDING_CANCEL]):
            self.logger().info(tracked_order.build_order_created_message())
            self._trigger_created_event(tracked_order)

    def _trigger_order_fills(self,
                             tracked_order: InFlightOrder,
                             prev_executed_amount_base: Decimal,
                             fill_amount: Decimal,
                             fill_price: Decimal,
                             fill_fee: TradeFeeBase,
                             trade_id: str,
                             exchange_order_id: str):
        if prev_executed_amount_base < tracked_order.executed_amount_base:
            self.logger().info(
                f"The {tracked_order.trade_type.name.upper()} order {tracked_order.client_order_id} "
                f"amounting to {tracked_order.executed_amount_base}/{tracked_order.amount} {tracked_order.base_asset} "
                f"has been filled at {fill_price} {tracked_order.quote_asset}."
            )
            self._trigger_filled_event(
                order=tracked_order,
                fill_amount=fill_amount,
                fill_price=fill_price,
                fill_fee=fill_fee,
                trade_id=trade_id,
                exchange_order_id=exchange_order_id,
            )

    def _trigger_order_completion(self, tracked_order: InFlightOrder, order_update: Optional[OrderUpdate] = None):
        if tracked_order.is_open:
            return

        if tracked_order.is_cancelled:
            self._trigger_cancelled_event(tracked_order)
            self.logger().info(f"Successfully canceled order {tracked_order.client_order_id}.")

        elif tracked_order.is_filled:
            self._trigger_completed_event(tracked_order)
            self.logger().info(
                f"{tracked_order.trade_type.name.upper()} order {tracked_order.client_order_id} completely filled."
            )

        elif tracked_order.is_failure:
            self._trigger_failure_event(tracked_order)
            self.logger().info(f"Order {tracked_order.client_order_id} has failed. Order Update: {order_update}")

        self.stop_tracking_order(tracked_order.client_order_id)

    @staticmethod
    def _restore_order_from_json(serialized_order: Dict):
        order = InFlightOrder.from_json(serialized_order)
        return order
