from decimal import Decimal
from enum import Enum
from typing import Dict, List, Set

from hummingbot.strategy.data_types import HangingOrder
from hummingbot.strategy.strategy_base import StrategyBase
from collections import defaultdict

s_decimal_zero = Decimal(0)


class HangingOrdersAggregationType(Enum):
    NO_AGGREGATION = 0
    VOLUME_WEIGHTED = 1
    VOLUME_TIME_WEIGHTED = 2
    VOLUME_DISTANCE_WEIGHTED = 3


class CreatedPairOfOrders:
    def __init__(self, buy_price, sell_price):
        self._buy_price = buy_price
        self._sell_price = sell_price
        self._filled_buy = False
        self._filled_sell = False

    def contains_price(self, price, side):
        return (side == 'buy' and self._buy_price == price and not self._filled_buy) or\
               (side == 'sell' and self._sell_price == price and not self._filled_sell)

    def fill_side(self, side):
        if side == 'buy':
            self._filled_buy = True
        else:
            self._filled_sell = True

    def partially_filled(self):
        return (self._filled_buy and not self._filled_sell) or (not self._filled_buy and self._filled_sell)

    def get_unfilled_side(self):
        if self.partially_filled():
            if not self._filled_sell:
                return self._sell_price, 'sell'
            else:
                return self._buy_price, 'buy'


class HangingOrdersTracker:
    AGGREGATION_METHODS = {
        HangingOrdersAggregationType.NO_AGGREGATION: "_get_equivalent_orders_no_aggregation",
        HangingOrdersAggregationType.VOLUME_WEIGHTED: "_get_equivalent_order_volume_weighted",
        HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED: "_get_equivalent_order_volume_and_age_weighted",
        HangingOrdersAggregationType.VOLUME_DISTANCE_WEIGHTED: "_get_equivalent_order_volume_and_distance_weighted"
    }

    def __init__(self,
                 strategy: StrategyBase,
                 aggregation_method: HangingOrdersAggregationType = None,
                 orders: Dict[str, HangingOrder] = None):
        self.strategy = strategy
        self.aggregation_method = aggregation_method or HangingOrdersAggregationType.NO_AGGREGATION
        self.original_orders = orders or dict()
        self.equivalent_orders = dict()
        self.current_timestamp = s_decimal_zero
        self.current_created_pairs_of_orders = defaultdict(list)

    def add_order(self, hanging_order: HangingOrder):
        self.original_orders[hanging_order.order_id] = hanging_order

    def remove_order(self, order_id):
        if order_id in self.original_orders.keys():
            self.original_orders.pop(order_id)

    def remove_max_aged_orders(self) -> List[str]:
        """ Returns List[order_id] to be cancelled"""
        result = []
        max_age = getattr(self.strategy, "_max_order_age")
        if max_age:
            for order_id, order in self.original_orders.items():
                if order.age > max_age:
                    # self.strategy.cancel_order(order.order_id) # Don't need to cancel cause original orders are not present in strategy
                    self.remove_order(order_id)
        return result

    def set_aggregation_method(self, aggregation_method: HangingOrdersAggregationType):
        self.aggregation_method = aggregation_method

    def get_order_ages(self):
        return {order_id: order.age for order_id, order in self.original_orders.items()}

    def get_equivalent_orders(self) -> Dict[str, Dict[str, HangingOrder]]:
        """
        Final result will be a dictionary of Lists.
        -> Dictionary[trading_pair, Set: HangingOrder]
        """
        result = dict()
        for trading_pair, orders in self.orders_by_trading_pair:
            result[trading_pair] = getattr(self,
                                           self.AGGREGATION_METHODS.get(self.aggregation_method,
                                                                        self._get_equivalent_orders_no_aggregation)
                                           )(orders)
        return result

    def update_strategy_orders_with_equivalent_orders(self):
        for trading_pair, orders in self.strategy.hanging_orders:
            equivalent_orders_for_trading_pair = self.equivalent_orders.get(trading_pair, set())
            orders_to_cancel = orders.difference(equivalent_orders_for_trading_pair)
            orders_to_create = equivalent_orders_for_trading_pair.difference(orders)
            self.cancel_multiple_orders_in_strategy([o.order_id for o in orders_to_cancel])
            # In the future this should also apply to strategies with multiple trading_pairs to have an order proposal with trading_pair info
            self.execute_orders_in_strategy(orders_to_create)
            self.add_created_orders_to_strategy_hanging_orders(orders_to_create, trading_pair)

    def add_created_orders_to_strategy_hanging_orders(self, orders: Set[HangingOrder], trading_pair: str):
        # Need to do this in case strategy is cython based
        current_hanging_orders = self.strategy.hanging_orders
        current_hanging_orders[trading_pair].extend(orders)
        self.strategy.hanging_orders = current_hanging_orders

    def execute_orders_in_strategy(self, orders: Set[HangingOrder]):
        order_type = self.strategy.market_info.market.get_maker_order_type()
        for order in orders:
            if order.is_buy:
                bid_order_id = self.strategy.buy_with_specific_market(
                    self.strategy.market_info,
                    order.amount,
                    order_type=order_type,
                    price=order.price,
                    expiration_seconds=self.strategy.order_refresh_time
                )
                order.order_id = bid_order_id
            else:
                ask_order_id = self.strategy.sell_with_specific_market(
                    self.strategy.market_info,
                    order.amount,
                    order_type=order_type,
                    price=order.price,
                    expiration_seconds=self.strategy.order_refresh_time
                )
                order.order_id = ask_order_id

    def cancel_multiple_orders_in_strategy(self, order_ids: List[str]):
        for order_id in order_ids:
            self.strategy.cancel_order(order_id)

    def _get_equivalent_orders_no_aggregation(self, orders):
        return frozenset(orders)

    def _get_equivalent_order_volume_weighted(self, orders):
        # ToDo
        return frozenset(orders)

    def _get_equivalent_order_volume_and_age_weighted(self, orders):
        # ToDo
        return frozenset(orders)

    def _get_equivalent_order_volume_and_distance_weighted(self, orders):
        # ToDo
        return frozenset(orders)

    def _get_orders_for_trading_pair(self, trading_pair: str) -> Dict[str, HangingOrder]:
        return {k: v for k, v in self.original_orders.items() if v.trading_pair == trading_pair}

    @property
    def orders_by_trading_pair(self) -> Dict[str, Dict[str, HangingOrder]]:
        trading_pairs = {v.trading_pair for k, v in self.original_orders.items()}
        result = dict()
        for trading_pair in trading_pairs:
            result[trading_pair] = self._get_orders_for_trading_pair(trading_pair)
        return result

    def is_order_id_in_hanging_orders(self, order_id: str, trading_pair: str):
        return order_id in self.equivalent_orders[trading_pair]

    def add_current_pairs_of_proposal_orders_executed_by_strategy(self, trading_pair, pair: CreatedPairOfOrders):
        self.current_created_pairs_of_orders[trading_pair].append(pair)

    def did_fill_order(self, trading_pair, side):
        for pair in self.current_created_pairs_of_orders[trading_pair]:
            if pair.contains_price(*side):
                if side[1] == 'buy':
                    pair._filled_buy = True
                else:
                    pair._filled_sell = True

    def add_hanging_orders_based_on_partially_executed_pairs(self):
        for trading_pair, pairs in self.current_created_pairs_of_orders.items():
            for pair in pairs:
                if pair.partially_filled():
                    side = pair.get_unfilled_side()
                    price = side[0]
                    is_buy = side[1] == 'buy'
                    order_in_strategy = next((o for o in self.strategy.active_orders if (o.is_buy == is_buy and
                                                                                         o.price == price and
                                                                                         o.trading_pair == trading_pair)
                                              ))
                    self.add_order(HangingOrder(order_in_strategy.client_order_id,
                                                order_in_strategy.trading_pair,
                                                is_buy,
                                                price,
                                                order_in_strategy.quantity))
