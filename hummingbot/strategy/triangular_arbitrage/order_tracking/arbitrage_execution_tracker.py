import asyncio
import time
from collections import namedtuple
from decimal import Decimal

from hummingbot.core.event.events import TradeType

from hummingbot.strategy.triangular_arbitrage.order_tracking.order import Order
from hummingbot.strategy.triangular_arbitrage.order_tracking.order_state import OrderState

Action = namedtuple("Action", "action order")


class ArbitrageExecutionTracker:
    def __init__(self,
                 left: str,
                 bottom: str,
                 right: str,
                 next_trade_delay: float,
                 max_order_hang: float = 10.0,
                 max_order_unsent: float = 20.0):

        self._left = left
        self._bottom = bottom
        self._right = right
        self._trading_pair_to_order = {
            self._left: None,
            self._bottom: None,
            self._right: None,
        }
        self._reverse = False
        self._trade_delay = next_trade_delay
        self._lock = asyncio.Lock()
        self._last_trade_time = 0
        self._ready = True
        self._recovering = False
        self._max_order_hang = max_order_hang
        self._awaiting_hanging_order_completion = False
        self._hanging_orders = []
        self._max_order_unsent = max_order_unsent

    @property
    def reverse(self):
        return self._reverse

    # self._ready is set to false once execution begins. once the execution is finished
    # the reset function will set the last trade time so that this inequality can be true
    # after the specified trade delay
    @property
    def ready(self):
        if self._recovering:
            self._ready = (time.time() > self._last_trade_time + self._trade_delay)
            if self._ready:
                self._recovering = False
        return self._ready

    @property
    def finished(self):
        orders = list(self._trading_pair_to_order.values())
        if not any([order is None for order in orders]):
            forward_finished = all([order.state == OrderState.COMPLETE for order in orders])
            reverse_finished = all([order.state == OrderState.REVERSE_COMPLETE for order in orders])
            return forward_finished or reverse_finished
        else:
            return True

    @property
    def recovering(self):
        return self._recovering

    @property
    def trade_delay(self):
        return self._trade_delay

    @property
    def awaiting_hanging_order_completion(self):
        return self._awaiting_hanging_order_completion

    async def __aenter__(self):
        await self._lock.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()

    # set once execution begins
    def set_not_ready(self):
        self._ready = False

    def set_ready(self):
        self._ready = True

    def get_next_actions(self):
        actions = []

        if not self.reverse:
            # if there are orders that are hanging, we need to perform no further actions
            # until they are complete
            if self.awaiting_hanging_order_completion and len(self._hanging_orders) > 0:
                completion_order = self._hanging_orders.pop(0)
                self._trading_pair_to_order[completion_order.trading_pair] = completion_order
                return [Action("place", completion_order)]

            left = self._trading_pair_to_order[self._left]
            bottom = self._trading_pair_to_order[self._bottom]
            right = self._trading_pair_to_order[self._right]

            if left.state in [OrderState.PARTIAL_FILL, OrderState.ACTIVE]:
                now = time.time()
                if now > (left.time_activated + self._max_order_hang):
                    completion_order = self.complete_partial_order(left)
                    actions.append(Action("cancel", left))
                    self._trading_pair_to_order[completion_order.trading_pair] = completion_order
                    self._hanging_orders.append(completion_order)
                    self._awaiting_hanging_order_completion = True
            if bottom.state in [OrderState.PARTIAL_FILL, OrderState.ACTIVE]:
                now = time.time()
                if now > (bottom.time_activated + self._max_order_hang):
                    completion_order = self.complete_partial_order(bottom)
                    actions.append(Action("cancel", bottom))
                    self._trading_pair_to_order[completion_order.trading_pair] = completion_order
                    self._hanging_orders.append(completion_order)
                    self._awaiting_hanging_order_completion = True
            if right.state in [OrderState.PARTIAL_FILL, OrderState.ACTIVE]:
                now = time.time()
                if now > (right.time_activated + self._max_order_hang):
                    completion_order = self.complete_partial_order(right)
                    actions.append(Action("cancel", right))
                    self._trading_pair_to_order[completion_order.trading_pair] = completion_order
                    self._hanging_orders.append(completion_order)
                    self._awaiting_hanging_order_completion = True

            if left.state in [OrderState.UNSENT, OrderState.HANGING]:
                now = time.time()
                if now > left.time_conceived + self._max_order_unsent:
                    self.reverse_execution()
                    return []
                elif now > left.time_conceived + (self._max_order_unsent / 2.0):
                    if all([OrderState.COMPLETE == right.state, OrderState.COMPLETE == bottom.state]):
                        left = actions.append(Action("place_all_in", left))
                else:
                    actions.append(Action("place", left))
            if right.state in [OrderState.UNSENT, OrderState.HANGING]:
                now = time.time()
                if now > right.time_conceived + self._max_order_unsent:
                    self.reverse_execution()
                    return []
                elif now > right.time_conceived + (self._max_order_unsent / 2.0):
                    if all([OrderState.COMPLETE == left.state, OrderState.COMPLETE == bottom.state]):
                        right = actions.append(Action("place_all_in", right))
                else:
                    actions.append(Action("place", right))
            if bottom.state in [OrderState.UNSENT, OrderState.HANGING]:
                now = time.time()
                if now > bottom.time_conceived + self._max_order_unsent:
                    self.reverse_execution()
                    return []
                elif now > bottom.time_conceived + (self._max_order_unsent / 2.0):
                    if OrderState.COMPLETE in [left.state, right.state]:
                        bottom = actions.append(Action("place_all_in", bottom))
                else:
                    actions.append(Action("place", bottom))

            return actions
        else:
            for order in list(self._trading_pair_to_order.values()):
                if order.state in [OrderState.TO_CANCEL, OrderState.REVERSE_PARTIAL_TO_CANCEL]:
                    if order.id is not None:
                        actions.append(Action("cancel", order))
                    else:
                        # this will occur if the order is pending partial to full
                        # and unsent when execution is thrown in reverse. we declare
                        # it cancelled and reverse execution
                        self.cancel(order.trading_pair)
                elif order.state == OrderState.REVERSE_PENDING:
                    actions.append((Action("place", order)))

            return actions

    def fail(self, trading_pair: str):
        order = self._trading_pair_to_order[trading_pair]
        if order.state < OrderState.FAILED:
            order.state = OrderState.FAILED
            self.reverse_execution()
        elif order.state > OrderState.REVERSE_PENDING:
            order.state = OrderState.REVERSE_FAILED

    def cancel(self, trading_pair: str):
        order = self._trading_pair_to_order[trading_pair]
        if self.reverse:
            if order.state < OrderState.REVERSE_PENDING:
                order.state = OrderState.REVERSE_COMPLETE
            elif order.state == OrderState.REVERSE_PARTIAL_TO_CANCEL:
                reverse_order = self.reverse_order(order)
                self._trading_pair_to_order[trading_pair] = reverse_order
        else:
            # we will cancel hanging orders and place new ones
            # otherwise, this cancel indicates an error state
            if order.state not in [OrderState.PARTIAL_FILL, OrderState.PENDING_PARTIAL_TO_FULL, OrderState.HANGING]:
                order.state = OrderState.CANCELED
                self.reverse_execution()

    def reverse_execution(self):
        if not self._reverse:
            self._reverse = True
            order_dict = self._trading_pair_to_order.copy()
            for trading_pair, order in order_dict.items():
                if order.state == OrderState.COMPLETE:
                    reverse_order = self.reverse_order(order)
                    self._trading_pair_to_order[trading_pair] = reverse_order
                elif order.state in [OrderState.ACTIVE, OrderState.PENDING]:
                    order.state = OrderState.TO_CANCEL
                elif order.state in [OrderState.UNSENT, OrderState.CANCELED, OrderState.FAILED]:
                    order.state = OrderState.REVERSE_COMPLETE
                elif order.state in [OrderState.PARTIAL_FILL, OrderState.PENDING_PARTIAL_TO_FULL]:
                    order.state = OrderState.REVERSE_PARTIAL_TO_CANCEL
                elif order.state == OrderState.HANGING:
                    order.state = OrderState.REVERSE_COMPLETE

    def reverse_order(self, order) -> Order:
        current_amount: Decimal = order.amount - order.amount_remaining
        total_amount: Decimal = current_amount + order.previously_filled
        side = TradeType.BUY if order.side == TradeType.SELL else TradeType.SELL
        if order.price is not None:
            # generous prices to ensure order completion
            price: Decimal = Decimal('1.5') * order.price if side == TradeType.BUY else Decimal('0.5') * order.price
        else:
            price = None
        reverse_order = Order(order.trading_pair,
                              None,
                              price,
                              total_amount,
                              side,
                              OrderState.REVERSE_PENDING)
        return reverse_order

    def all_in_order(self, order, wallet_balance) -> Order:
        if order.side == TradeType.BUY:
            price = order.price * Decimal('1.1')
            amount = (wallet_balance / price) * Decimal('0.99')
        else:
            amount = wallet_balance
            price = order.price * Decimal('0.75')
        all_in_order = Order(order.trading_pair,
                             None,
                             price,
                             amount,
                             order.side,
                             order.state,
                             is_all_in=True)
        return all_in_order

    def complete_partial_order(self, order) -> Order:
        amount: Decimal = order.amount_remaining
        previously_filled: Decimal = order.amount - amount
        if order.side == TradeType.BUY:
            # generous prices to ensure order completion
            price = order.price * Decimal('1.5')
        else:
            price = order.price * Decimal('0.75')
        if amount == order.amount:
            completion_order = Order(order.trading_pair,
                                     None,
                                     price,
                                     amount,
                                     order.side,
                                     OrderState.HANGING,
                                     previously_filled)
        else:
            completion_order = Order(order.trading_pair,
                                     None,
                                     price,
                                     amount,
                                     order.side,
                                     OrderState.PENDING_PARTIAL_TO_FULL,
                                     previously_filled)
        return completion_order

    def order_complete(self, id: str, trading_pair: str):
        order = self._trading_pair_to_order[trading_pair]
        if order.state < OrderState.COMPLETE:
            if order.state in [OrderState.PENDING_PARTIAL_TO_FULL, OrderState.HANGING]:
                if len(self._hanging_orders) < 1:
                    self._awaiting_hanging_order_completion = False
            order.state = OrderState.COMPLETE
            if self.reverse:
                self._trading_pair_to_order[trading_pair] = self.reverse_order(order)
        elif order.state >= OrderState.REVERSE_UNSENT:
            order.state = OrderState.REVERSE_COMPLETE

    def fill(self, trading_pair: str, amount_filled: Decimal):
        order = self._trading_pair_to_order[trading_pair]
        order.amount_remaining -= amount_filled
        if not self.reverse:
            if order.amount_remaining > Decimal('0') and order.state < OrderState.COMPLETE:
                order.state = OrderState.PARTIAL_FILL

    def add_opportunity(self, arbitrage_opportunity):
        order_1, order_2, order_3, *_ = arbitrage_opportunity

        first_order = Order(order_1.trading_pair, None, self.price_markup(order_1), order_1.amount, order_1.trade_type)
        self._trading_pair_to_order[order_1.trading_pair] = first_order

        second_order = Order(order_2.trading_pair, None, self.price_markup(order_2), order_2.amount, order_2.trade_type)
        self._trading_pair_to_order[order_2.trading_pair] = second_order

        third_order = Order(order_3.trading_pair, None, self.price_markup(order_3), order_3.amount, order_3.trade_type)
        self._trading_pair_to_order[order_3.trading_pair] = third_order

        return first_order, second_order, third_order

    def price_markup(self, order: Order, markup: Decimal = Decimal('0.001')):
        if order.trade_type == TradeType.BUY:
            return (Decimal('1') + markup) * order.price
        else:
            return (Decimal('1') - markup) * order.price

    def update_order_id(self, trading_pair, order_id):
        order: Order = self._trading_pair_to_order[trading_pair]
        order.update_order_id(order_id)

    def order_placed(self, trading_pair):
        order = self._trading_pair_to_order[trading_pair]
        if order.state < OrderState.ACTIVE:
            order.mark_active()
        elif order.state > OrderState.REVERSE_UNSENT:
            order.state = OrderState.REVERSE_ACTIVE

    def reset(self, override_recovery: bool = False):
        self._reverse = False
        if not override_recovery:
            self._recovering = True
            self._last_trade_time = time.time()
        self._awaiting_hanging_order_completion = False
        self._hanging_orders = []
