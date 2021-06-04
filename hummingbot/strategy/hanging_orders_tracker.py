import logging
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Set

from hummingbot.strategy.data_types import HangingOrder
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.core.data_type.limit_order import LimitOrder

s_decimal_zero = Decimal(0)
sb_logger = None


class HangingOrdersAggregationType(Enum):
    NO_AGGREGATION = 0
    VOLUME_WEIGHTED = 1
    VOLUME_TIME_WEIGHTED = 2
    VOLUME_DISTANCE_WEIGHTED = 3


class CreatedPairOfOrders:
    def __init__(self, buy_order: LimitOrder, sell_order: LimitOrder):
        self.buy_order = buy_order
        self.sell_order = sell_order
        self.filled_buy = False
        self.filled_sell = False

    def contains_order(self, order: LimitOrder):
        return ((self.buy_order is not None) and (self.buy_order.client_order_id == order.client_order_id)) or \
               ((self.sell_order is not None) and (self.sell_order.client_order_id == order.client_order_id))

    def partially_filled(self):
        return (self.filled_buy and not self.filled_sell) or (not self.filled_buy and self.filled_sell)

    def get_unfilled_order(self):
        if self.partially_filled():
            if not self.filled_buy:
                return self.buy_order
            else:
                return self.sell_order


class HangingOrdersTracker:
    AGGREGATION_METHODS = {
        HangingOrdersAggregationType.NO_AGGREGATION: "_get_equivalent_orders_no_aggregation",
        HangingOrdersAggregationType.VOLUME_WEIGHTED: "_get_equivalent_order_volume_weighted",
        HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED: "_get_equivalent_order_volume_and_age_weighted",
        HangingOrdersAggregationType.VOLUME_DISTANCE_WEIGHTED: "_get_equivalent_order_volume_and_distance_weighted"
    }

    @classmethod
    def logger(cls):
        global sb_logger
        if sb_logger is None:
            sb_logger = logging.getLogger(__name__)
        return sb_logger

    def __init__(self,
                 strategy: StrategyBase,
                 aggregation_method: HangingOrdersAggregationType = None,
                 hanging_orders_cancel_pct=None,
                 orders: Dict[str, HangingOrder] = None,
                 trading_pair: str = None):
        self.strategy = strategy
        self.aggregation_method = aggregation_method or HangingOrdersAggregationType.NO_AGGREGATION
        self._hanging_orders_cancel_pct = hanging_orders_cancel_pct or Decimal("0.1")
        self.trading_pair = trading_pair or self.strategy.trading_pair
        self.current_created_pairs_of_orders = list()
        self.original_orders: Set[LimitOrder] = orders or set()
        self.strategy_current_hanging_orders: Set[HangingOrder] = set()

    def add_order(self, hanging_order: LimitOrder):
        self.original_orders.add(hanging_order)

    def remove_order(self, order: LimitOrder):
        if order in self.original_orders:
            self.original_orders.remove(order)

    def remove_all_orders(self):
        self.original_orders.clear()

    def renew_hanging_orders_past_max_order_age(self):
        max_age = getattr(self.strategy, "max_order_age", None)
        to_be_renewed = set()
        if max_age:
            for order in self.strategy_current_hanging_orders:
                if order.age > max_age:
                    self.logger().info(f"Reached max_order_age={max_age}sec hanging order: {order}. Renewing...")
                    to_be_renewed.add(order)

            self.cancel_multiple_orders_in_strategy([o.order_id for o in to_be_renewed if o.order_id])
            for order in to_be_renewed:
                self.strategy_current_hanging_orders.remove(order)

            executed_orders = self.execute_orders_in_strategy(to_be_renewed)
            self.strategy_current_hanging_orders = self.strategy_current_hanging_orders.union(executed_orders)

    def remove_orders_far_from_price(self):
        current_price = self.strategy.get_price()
        orders_to_be_removed = set()
        for order in self.original_orders:
            if order.distance_to_price(current_price) / current_price > self._hanging_orders_cancel_pct:
                self.logger().info(
                    f"Hanging order passed max_distance from price={self._hanging_orders_cancel_pct * 100}% {order}. Removing...")
                orders_to_be_removed.add(order)
        for order in orders_to_be_removed:
            self.remove_order(order)

    def set_aggregation_method(self, aggregation_method: HangingOrdersAggregationType):
        self.aggregation_method = aggregation_method

    def get_equivalent_orders(self) -> Set[HangingOrder]:
        if self.original_orders:
            return getattr(self,
                           self.AGGREGATION_METHODS.get(self.aggregation_method,
                                                        "_get_equivalent_orders_no_aggregation"))(self.original_orders)
        return set()

    @property
    def equivalent_orders(self):
        return self.get_equivalent_orders()

    def is_order_id_in_hanging_orders(self, order_id: str):
        return any((o.order_id == order_id for o in self.strategy_current_hanging_orders))

    def update_strategy_orders_with_equivalent_orders(self):
        equivalent_orders = self.get_equivalent_orders()
        orders_to_cancel = self.strategy_current_hanging_orders.difference(equivalent_orders)
        orders_to_create = equivalent_orders.difference(self.strategy_current_hanging_orders)
        self.cancel_multiple_orders_in_strategy([o.order_id for o in orders_to_cancel])
        executed_orders = self.execute_orders_in_strategy(orders_to_create)
        self.add_created_orders_to_strategy_hanging_orders(executed_orders)

        if any((orders_to_cancel, orders_to_create)):
            self.logger().info("Updating hanging orders...")
            self.logger().info(f"Original hanging orders: {self.original_orders}")
            self.logger().info(f"Equivalent hanging orders: {self.equivalent_orders}")

    def add_created_orders_to_strategy_hanging_orders(self, orders: Set[HangingOrder]):
        self.strategy_current_hanging_orders = self.strategy_current_hanging_orders.union(orders)

    def execute_orders_in_strategy(self, candidate_orders: Set[HangingOrder]):
        """ToDo: Need to verify budget restriction.
        Specially when execution of orders happens after they were cancelled to be renewed.
        In that case we are not waiting for orders to be successfully cancelled before creating the new ones
        and that might lead to lack of budget."""
        # Currently prioritizing hanging orders and then creating orders with remaining balance
        executed_orders = set()
        order_type = self.strategy.market_info.market.get_maker_order_type()
        for order in candidate_orders:
            quantized_amount = self.strategy.market_info.market.quantize_order_amount(self.trading_pair, order.amount)
            quantized_price = self.strategy.market_info.market.quantize_order_price(self.trading_pair, order.price)
            if quantized_amount > 0:
                if order.is_buy:
                    order_id = self.strategy.buy_with_specific_market(
                        self.strategy.market_info,
                        amount=quantized_amount,
                        order_type=order_type,
                        price=quantized_price,
                        expiration_seconds=self.strategy.order_refresh_time
                    )
                else:
                    order_id = self.strategy.sell_with_specific_market(
                        self.strategy.market_info,
                        amount=quantized_amount,
                        order_type=order_type,
                        price=quantized_price,
                        expiration_seconds=self.strategy.order_refresh_time
                    )
                executed_orders.add(HangingOrder(order_id, order.trading_pair, order.is_buy, quantized_price, quantized_amount))
        return executed_orders

    def cancel_multiple_orders_in_strategy(self, order_ids: List[str]):
        for order_id in order_ids:
            if any(o.client_order_id == order_id for o in self.strategy.active_orders):
                self.strategy.cancel_order(order_id)

    def _get_equivalent_orders_no_aggregation(self, orders):
        return frozenset(orders)

    def _obtain_equivalent_weighted_order(self, orders, weight_function):
        buys = [o for o in orders if o.is_buy]
        sells = [o for o in orders if not o.is_buy]
        current_price = self.strategy.get_price()
        distance_prod_subs = sum(abs(current_price - o.price) * o.amount * weight_function(o) for o in sells) -\
            sum(abs(current_price - o.price) * o.amount * weight_function(o) for o in buys)
        if distance_prod_subs != 0:
            isbuy = distance_prod_subs < 0
            price = current_price + distance_prod_subs / sum(o.amount * weight_function(o) for o in orders)
            amount_sum = sum(o.amount * weight_function(o) for o in orders)
            amount = (sum(o.amount for o in sells) * sum(o.amount * weight_function(o) for o in sells) -
                      sum(o.amount for o in buys) * sum(o.amount * weight_function(o) for o in buys)) / amount_sum

            return frozenset([HangingOrder(None, self.trading_pair, isbuy, price, amount)])
        return frozenset()

    def _get_equivalent_order_volume_weighted(self, orders: Set[LimitOrder]):
        return self._obtain_equivalent_weighted_order(orders, lambda o: Decimal("1"))

    def _get_equivalent_order_volume_and_age_weighted(self, orders: Set[LimitOrder]):
        max_order_age = getattr(self.strategy, "max_order_age", lambda: None)
        if max_order_age:
            return self._obtain_equivalent_weighted_order(orders,
                                                          lambda o: Decimal.exp(-Decimal(str(o.age / max_order_age))))
        return frozenset()

    def _get_equivalent_order_volume_and_distance_weighted(self, orders: Set[LimitOrder]):
        current_price = self.strategy.get_price()
        return self._obtain_equivalent_weighted_order(orders,
                                                      lambda o: Decimal.exp(-Decimal(str(abs(o.price - current_price)
                                                                                         / current_price))))

    def add_current_pairs_of_proposal_orders_executed_by_strategy(self, pair: CreatedPairOfOrders):
        self.current_created_pairs_of_orders.append(pair)

    def did_fill_order(self, order: LimitOrder):
        for pair in self.current_created_pairs_of_orders:
            if pair.contains_order(order):
                if order.is_buy:
                    pair.filled_buy = True
                else:
                    pair.filled_sell = True

    def did_fill_hanging_order(self, order: LimitOrder):
        order_to_be_removed = next(o for o in self.strategy_current_hanging_orders
                                   if o == HangingOrder(order.client_order_id,
                                                        order.trading_pair,
                                                        order.is_buy,
                                                        order.price,
                                                        order.quantity))
        if order_to_be_removed:
            self.strategy_current_hanging_orders.remove(order_to_be_removed)
        if self.aggregation_method == HangingOrdersAggregationType.NO_AGGREGATION.name:
            self.remove_order(order)
        else:
            # For any aggregation other than no_aggregation, the hanging order is the equivalent to all original
            # hanging orders
            self.remove_all_orders()

    def add_hanging_orders_based_on_partially_executed_pairs(self):
        for pair in self.current_created_pairs_of_orders:
            if pair.partially_filled():
                unfilled_order = pair.get_unfilled_order()
                # Check if the unfilled order is in active_orders because it might have failed before being created
                if unfilled_order in self.strategy.active_orders:
                    self.add_hanging_order_based_on_limit_order(unfilled_order)
        self.current_created_pairs_of_orders.clear()

    def add_hanging_order_based_on_limit_order(self, order: LimitOrder):
        self.add_order(HangingOrder(order.client_order_id,
                                    order.trading_pair,
                                    order.is_buy,
                                    order.price,
                                    order.quantity))
