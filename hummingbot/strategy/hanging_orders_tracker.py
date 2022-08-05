import logging
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderCancelledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.data_types import HangingOrder
from hummingbot.strategy.strategy_base import StrategyBase

s_decimal_zero = Decimal(0)
sb_logger = None


class CreatedPairOfOrders:
    def __init__(self, buy_order: Optional[LimitOrder], sell_order: Optional[LimitOrder], buy_fill: bool = False,
                 sell_fill: bool = False):
        self.buy_order = buy_order
        self.sell_order = sell_order
        self.filled_buy = buy_fill
        self.filled_sell = sell_fill

    def contains_order(self, order_id: str):
        return ((self.buy_order is not None) and (self.buy_order.client_order_id == order_id)) or \
               ((self.sell_order is not None) and (self.sell_order.client_order_id == order_id))

    def partially_filled(self):
        return self.filled_buy != self.filled_sell

    def get_unfilled_order(self):
        if self.partially_filled():
            if not self.filled_buy:
                return self.buy_order
            else:
                return self.sell_order


class OrdS(Enum):
    BUY = 1
    SELL = 2


class HangingOrdersTracker:

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global sb_logger
        if sb_logger is None:
            sb_logger = logging.getLogger(__name__)
        return sb_logger

    def __init__(self,
                 strategy: StrategyBase,
                 hanging_orders_cancel_pct=None,
                 orders: Dict[str, HangingOrder] = None,
                 trading_pair: str = None,
                 hanging_buy_orders_cancel_pct=None,
                 hanging_sell_orders_cancel_pct=None,
                 ):
        self.strategy: StrategyBase = strategy
        self._hanging_buy_orders_cancel_pct: Decimal = hanging_buy_orders_cancel_pct or hanging_orders_cancel_pct or Decimal(
            "0.1")
        self._hanging_sell_orders_cancel_pct: Decimal = hanging_sell_orders_cancel_pct or hanging_orders_cancel_pct or Decimal(
            "0.1")
        self.trading_pair: str = trading_pair or self.strategy.trading_pair
        self.orders_being_renewed: Set[HangingOrder] = set()
        self.orders_being_cancelled: Set[str] = set()
        self.current_created_pairs_of_orders: List[CreatedPairOfOrders] = list()
        self.original_orders: Set[LimitOrder] = orders or set()
        self._strategy_current_hanging_orders: Dict[OrdS, Set[HangingOrder]] = dict()
        self._strategy_current_hanging_orders[OrdS.BUY]: Set[HangingOrder] = set()
        self._strategy_current_hanging_orders[OrdS.SELL]: Set[HangingOrder] = set()
        self._completed_hanging_orders: Dict[OrdS, Set[HangingOrder]] = dict(set())
        self._completed_hanging_orders[OrdS.BUY]: Set[HangingOrder] = set()
        self._completed_hanging_orders[OrdS.SELL]: Set[HangingOrder] = set()

        self._cancel_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_cancel_order)
        self._complete_buy_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_complete_buy_order)
        self._complete_sell_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_complete_sell_order)
        self._event_pairs: List[Tuple[MarketEvent, SourceInfoEventForwarder]] = [
            (MarketEvent.OrderCancelled, self._cancel_order_forwarder),
            (MarketEvent.BuyOrderCompleted, self._complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._complete_sell_order_forwarder)]

    @property
    def hanging_orders_cancel_pct(self):
        self.logger().warning("The HangingOrder class is asymmetric, select buy or sell method.\n"
                              "This method is being obsoleted.")
        if self._hanging_buy_orders_cancel_pct != self._hanging_sell_orders_cancel_pct:
            self.logger().error("This method returns an incorrect value for asymmetric HangingOrder.")
        return (self._hanging_buy_orders_cancel_pct + self._hanging_sell_orders_cancel_pct) * Decimal("0.5")

    @hanging_orders_cancel_pct.setter
    def hanging_orders_cancel_pct(self, value):
        self.logger().warning("The HangingOrder class is asymmetric, select buy or sell method.\n"
                              "This method is being obsoleted.")
        self._hanging_buy_orders_cancel_pct = value
        self._hanging_sell_orders_cancel_pct = value

    @property
    def hanging_buy_orders_cancel_pct(self):
        return self._hanging_buy_orders_cancel_pct

    @hanging_buy_orders_cancel_pct.setter
    def hanging_buy_orders_cancel_pct(self, value: Decimal):
        if not value.is_nan():
            self._hanging_buy_orders_cancel_pct = max(s_decimal_zero, value)
        else:
            self._hanging_buy_orders_cancel_pct = value

    @property
    def hanging_sell_orders_cancel_pct(self):
        return self._hanging_sell_orders_cancel_pct

    @hanging_sell_orders_cancel_pct.setter
    def hanging_sell_orders_cancel_pct(self, value: Decimal):
        if not value.is_nan():
            self._hanging_sell_orders_cancel_pct = max(s_decimal_zero, value)
        else:
            self._hanging_sell_orders_cancel_pct = value

    @property
    def strategy_current_hanging_orders(self):
        return self._current_ho

    @property
    def completed_hanging_orders(self):
        return self._completed_ho

    # Shortcuts
    @property
    def _current_ho(self):
        return self._strategy_current_hanging_orders[OrdS.BUY].union(self._strategy_current_hanging_orders[OrdS.SELL])

    @property
    def _completed_ho(self):
        return self._completed_hanging_orders[OrdS.BUY].union(self._completed_hanging_orders[OrdS.SELL])

    def register_events(self, markets: List[ConnectorBase]):
        """Start listening to events from the given markets."""
        for market in markets:
            for event_pair in self._event_pairs:
                market.add_listener(event_pair[0], event_pair[1])

    def unregister_events(self, markets: List[ConnectorBase]):
        """Stop listening to events from the given market."""
        for market in markets:
            for event_pair in self._event_pairs:
                market.remove_listener(event_pair[0], event_pair[1])

    def _did_cancel_order(self,
                          event_tag: int,
                          market: ConnectorBase,
                          event: OrderCancelledEvent):

        self._process_cancel_as_part_of_renew(event)

        self.orders_being_cancelled.discard(event.order_id)

        # Removing buy/sell orders
        order_to_be_removed = next((o for o in self._current_ho if o.order_id == event.order_id), None)

        if order_to_be_removed in self._strategy_current_hanging_orders[OrdS.BUY]:
            self._strategy_current_hanging_orders[OrdS.BUY].remove(order_to_be_removed)
            self.logger().notify(f"({self.trading_pair}) Hanging BUY order {event.order_id} canceled.")

        if order_to_be_removed in self._strategy_current_hanging_orders[OrdS.SELL]:
            self._strategy_current_hanging_orders[OrdS.SELL].remove(order_to_be_removed)
            self.logger().notify(f"({self.trading_pair}) Hanging SELL order {event.order_id} canceled.")

        limit_order_to_be_removed = next((order for order in self.original_orders
                                          if order.client_order_id == event.order_id), None)
        if limit_order_to_be_removed:
            self.remove_order(limit_order_to_be_removed)

    def _did_complete_buy_order(self,
                                event_tag: int,
                                market: ConnectorBase,
                                event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        self._did_complete_order(event, True)

    def _did_complete_sell_order(self,
                                 event_tag: int,
                                 market: ConnectorBase,
                                 event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        self._did_complete_order(event, False)

    def _did_complete_order(self,
                            event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent],
                            is_buy: bool):
        hanging_order = next((ho for ho in self._current_ho if ho.order_id == event.order_id), None)
        if hanging_order:
            self._did_complete_hanging_order(hanging_order)
        else:
            for pair in self.current_created_pairs_of_orders:
                if pair.contains_order(event.order_id):
                    pair.filled_buy = pair.filled_buy or is_buy
                    pair.filled_sell = pair.filled_sell or not is_buy

    def _did_complete_hanging_order(self, order: HangingOrder):

        if order:
            if order.is_buy:
                order_side = "BUY"
                self._completed_hanging_orders[OrdS.BUY].add(order)
                self._strategy_current_hanging_orders[OrdS.BUY].remove(order)
            else:
                order_side = "SELL"
                self._completed_hanging_orders[OrdS.SELL].add(order)
                self._strategy_current_hanging_orders[OrdS.SELL].remove(order)

            self.logger().notify(
                f"({self.trading_pair}) Hanging maker {order_side} order {order.order_id} "
                f"({order.trading_pair} {order.amount} @ "
                f"{order.price}) has been completely filled."
            )

            limit_order_to_be_removed = next((original_order for original_order in self.original_orders
                                              if original_order.client_order_id == order.order_id), None)
            if limit_order_to_be_removed:
                self.remove_order(limit_order_to_be_removed)

    def process_tick(self):
        """Updates the currently active hanging orders.

        Removes active and pending hanging orders with prices that have surpassed
        the cancelation percent and renews active hanging orders that have passed
        the max order age.

        This method should be called on each clock tick.
        """
        self.remove_orders_far_from_price()
        self.renew_hanging_orders_past_max_order_age()

    def _process_cancel_as_part_of_renew(self, event: OrderCancelledEvent):
        renewing_order = next((order for order in self.orders_being_renewed if order.order_id == event.order_id), None)
        if renewing_order:
            if renewing_order.is_buy:
                self.logger().info(f"({self.trading_pair}) Hanging BUY order {event.order_id} "
                                   f"has been canceled as part of the renew process. "
                                   f"Now the replacing order will be created.")
                self._strategy_current_hanging_orders[OrdS.BUY].remove(renewing_order)
            else:
                self.logger().info(f"({self.trading_pair}) Hanging SELL order {event.order_id} "
                                   f"has been canceled as part of the renew process. "
                                   f"Now the replacing order will be created.")
                self._strategy_current_hanging_orders[OrdS.SELL].remove(renewing_order)

            self.orders_being_renewed.remove(renewing_order)
            order_to_be_created = HangingOrder(None,
                                               renewing_order.trading_pair,
                                               renewing_order.is_buy,
                                               renewing_order.price,
                                               renewing_order.amount,
                                               self.strategy.current_timestamp)

            executed_orders = self._execute_orders_in_strategy({order_to_be_created})
            if renewing_order.is_buy:
                self._strategy_current_hanging_orders[OrdS.BUY] = self._strategy_current_hanging_orders[OrdS.BUY].union(
                    {o for o in executed_orders if o.is_buy})
            else:
                self._strategy_current_hanging_orders[OrdS.BUY] = self._strategy_current_hanging_orders[
                    OrdS.SELL].union(
                    {o for o in executed_orders if not o.is_buy})

            for new_hanging_order in executed_orders:
                limit_order_from_hanging_order = next((o for o in self.strategy.active_orders
                                                       if o.client_order_id == new_hanging_order.order_id), None)
                if limit_order_from_hanging_order:
                    self.add_order(limit_order_from_hanging_order)

    def add_order(self, order: LimitOrder):
        self.original_orders.add(order)

    def add_as_hanging_order(self, order: LimitOrder):
        if order.is_buy:
            self._strategy_current_hanging_orders[OrdS.BUY].add(self._get_hanging_order_from_limit_order(order))
        else:
            self._strategy_current_hanging_orders[OrdS.SELL].add(self._get_hanging_order_from_limit_order(order))
        self.add_order(order)

    def remove_order(self, order: LimitOrder):
        if order in self.original_orders:
            self.original_orders.remove(order)

    def remove_all_orders(self):
        self.original_orders.clear()

    def remove_all_buys(self):
        to_be_removed = []
        for order in self.original_orders:
            if order.is_buy:
                to_be_removed.append(order)
        for order in to_be_removed:
            self.original_orders.remove(order)

    def remove_all_sells(self):
        to_be_removed = []
        for order in self.original_orders:
            if not order.is_buy:
                to_be_removed.append(order)
        for order in to_be_removed:
            self.original_orders.remove(order)

    def hanging_order_age(self, hanging_order: HangingOrder) -> float:
        """
        Returns the number of seconds between the current time (taken from the strategy) and the order creation time
        """
        return (self.strategy.current_timestamp - hanging_order.creation_timestamp
                if hanging_order.creation_timestamp
                else -1)

    def renew_hanging_orders_past_max_order_age(self):
        to_be_cancelled: Set[HangingOrder] = set()
        max_order_age = getattr(self.strategy, "max_order_age", None)
        if max_order_age:
            for order in self._current_ho:
                if self.hanging_order_age(order) > max_order_age and order not in self.orders_being_renewed:
                    self.logger().info(f"Reached max_order_age={max_order_age}sec hanging order: {order}. Renewing...")
                    to_be_cancelled.add(order)

            self._cancel_multiple_orders_in_strategy([o.order_id for o in to_be_cancelled if o.order_id])
            self.orders_being_renewed = self.orders_being_renewed.union(to_be_cancelled)

    def remove_orders_far_from_price(self):
        current_price = self.strategy.get_price()
        orders_to_be_removed = set()
        for order in self.original_orders:
            if (order.client_order_id not in self.orders_being_cancelled
                    and order.is_buy and abs(
                        order.price - current_price) / current_price > self._hanging_buy_orders_cancel_pct):
                self.logger().info(
                    f"Hanging BUY order passed max_distance from price={self._hanging_buy_orders_cancel_pct * 100}% {order}. Removing...")
                orders_to_be_removed.add(order)
            if (order.client_order_id not in self.orders_being_cancelled
                    and not order.is_buy and abs(
                        order.price - current_price) / current_price > self._hanging_sell_orders_cancel_pct):
                self.logger().info(
                    f"Hanging SELL order passed max_distance from price={self._hanging_sell_orders_cancel_pct * 100}% {order}. Removing...")
                orders_to_be_removed.add(order)

        self._cancel_multiple_orders_in_strategy([order.client_order_id for order in orders_to_be_removed])

    def _get_equivalent_orders(self) -> Set[HangingOrder]:
        if self.original_orders:
            return self._get_equivalent_orders_no_aggregation(self.original_orders)
        return set()

    @property
    def equivalent_orders(self) -> Set[HangingOrder]:
        """Creates a list of `HangingOrder`s from the registered `LimitOrder`s."""
        return self._get_equivalent_orders()

    def is_order_id_in_hanging_orders(self, order_id: str) -> bool:
        return any((o.order_id == order_id for o in self.strategy_current_hanging_orders))

    def is_order_id_in_completed_hanging_orders(self, order_id: str) -> bool:
        return any((o.order_id == order_id for o in self.completed_hanging_orders))

    def is_hanging_order_in_strategy_active_orders(self, order: HangingOrder) -> bool:
        return any(all([order.trading_pair == o.trading_pair,
                        order.is_buy == o.is_buy,
                        order.price == o.price,
                        order.amount == o.quantity]) for o in self.strategy.active_orders)

    def is_potential_hanging_order(self, order: LimitOrder) -> bool:
        """Checks if the order is registered as a hanging order."""
        return order in self.original_orders

    def update_strategy_orders_with_equivalent_orders(self):
        """Updates the strategy hanging orders.

        Checks the internal list of hanging orders that should exist for the strategy
        and ensures that those orders do exist by creating/canceling orders
        within the strategy accordingly.
        """

        self._add_hanging_orders_based_on_partially_executed_pairs()

        equivalent_orders = self.equivalent_orders

        orders_to_create = equivalent_orders.difference(self._current_ho)
        orders_to_cancel = self._current_ho.difference(equivalent_orders)

        self._cancel_multiple_orders_in_strategy([o.order_id for o in orders_to_cancel])

        if any((orders_to_cancel, orders_to_create)):
            self.logger().info("Updating hanging orders...")
            self.logger().info(f"Original hanging orders: {self.original_orders}")
            self.logger().info(f"Equivalent hanging orders: {equivalent_orders}")
            self.logger().info(f"Need to create: {orders_to_create}")
            self.logger().info(f"Need to cancel: {orders_to_cancel}")

        executed_orders = self._execute_orders_in_strategy(orders_to_create)
        self._strategy_current_hanging_orders[OrdS.BUY] = self._strategy_current_hanging_orders[OrdS.BUY].union(
            {e for e in executed_orders if e.is_buy})
        self._strategy_current_hanging_orders[OrdS.SELL] = self._strategy_current_hanging_orders[OrdS.SELL].union(
            {e for e in executed_orders if not e.is_buy})

    def _execute_orders_in_strategy(self, candidate_orders: Set[HangingOrder]):
        new_hanging_orders = set()
        order_type = self.strategy.market_info.market.get_maker_order_type()
        for order in candidate_orders:
            # Only execute if order is new
            if order.order_id is None:
                if order.amount > 0:
                    if order.is_buy:
                        order_id = self.strategy.buy_with_specific_market(
                            self.strategy.market_info,
                            amount=order.amount,
                            order_type=order_type,
                            price=order.price,
                            expiration_seconds=self.strategy.order_refresh_time
                        )
                    else:
                        order_id = self.strategy.sell_with_specific_market(
                            self.strategy.market_info,
                            amount=order.amount,
                            order_type=order_type,
                            price=order.price,
                            expiration_seconds=self.strategy.order_refresh_time
                        )
                    new_hanging_order = HangingOrder(order_id,
                                                     order.trading_pair,
                                                     order.is_buy,
                                                     order.price,
                                                     order.amount,
                                                     self.strategy.current_timestamp)

                    new_hanging_orders.add(new_hanging_order)
            # If it's a preexistent order we don't create it but we add it to hanging orders
            else:
                new_hanging_orders.add(order)
        return new_hanging_orders

    def _cancel_multiple_orders_in_strategy(self, order_ids: List[str]):
        for order_id in order_ids:
            if any(o.client_order_id == order_id for o in self.strategy.active_orders):
                self.strategy.cancel_order(order_id)
                self.orders_being_cancelled.add(order_id)

    def _get_equivalent_orders_no_aggregation(self, orders):
        return frozenset(self._get_hanging_order_from_limit_order(o) for o in orders)

    def add_current_pairs_of_proposal_orders_executed_by_strategy(self, pair: CreatedPairOfOrders):
        self.current_created_pairs_of_orders.append(pair)

    def _add_hanging_orders_based_on_partially_executed_pairs(self):
        for unfilled_order in self.candidate_hanging_orders_from_pairs():
            self.add_order(unfilled_order)
        self.current_created_pairs_of_orders.clear()

    def _get_hanging_order_from_limit_order(self, order: LimitOrder):
        return HangingOrder(
            order.client_order_id,
            order.trading_pair,
            order.is_buy,
            order.price,
            order.quantity,
            order.creation_timestamp * 1e-6)

    def candidate_hanging_orders_from_pairs(self):
        candidate_orders = []
        for pair in self.current_created_pairs_of_orders:
            if pair.partially_filled():
                unfilled_order = pair.get_unfilled_order()
                # Check if the unfilled order is in active_orders because it might have failed before being created
                if unfilled_order in self.strategy.active_orders:
                    candidate_orders.append(unfilled_order)
        return candidate_orders
