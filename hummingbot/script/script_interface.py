from decimal import Decimal

child_queue = None


def set_child_queue(queue):
    global child_queue
    child_queue = queue


class PMMParameter(object):

    def __init__(self, attr):
        self.name = attr
        self.attr = "_" + attr
        self.updated_value = None

    def __get__(self, obj, objtype):
        return getattr(obj, self.attr)

    def __set__(self, obj, value):
        global child_queue
        old_value = getattr(obj, self.attr)
        if old_value is not None and old_value != value:
            print(f"attr old {old_value} new {value}")
            self.updated_value = value
            child_queue.put(self)
        # print(f"{obj.__class__} {self.attr} {value}")
        setattr(obj, self.attr, value)

    def __repr__(self):
        return str(self.__dict__)


class PMMParameters:
    def __init__(self):
        self._buy_levels = None
        self._sell_levels = None
        self._order_levels = None
        self._bid_spread = None
        self._ask_spread = None
        self._order_amount = None
        self._order_level_spread = None
        self._order_level_amount = None
        self._order_refresh_time = None
        self._order_refresh_tolerance_pct = None
        self._filled_order_delay = None
        # self._inventory_skew_enabled = None
        # self._inventory_target_base_pct = None
        # self._inventory_range_multiplier = None
        # self._hanging_orders_enabled = None
        # self._hanging_orders_cancel_pct = None
        # self._order_optimization_enabled = None
        # self._ask_order_optimization_depth = None
        # self._bid_order_optimization_depth = None
        # self._add_transaction_costs_to_orders = None
        # self._price_ceiling = None
        # self._price_floor = None
        # self._ping_pong_enabled = None
        # self._minimum_spread = None

    buy_levels = PMMParameter("buy_levels")
    sell_levels = PMMParameter("sell_levels")
    order_levels = PMMParameter("order_levels")
    bid_spread = PMMParameter("bid_spread")
    ask_spread = PMMParameter("ask_spread")
    order_amount = PMMParameter("order_amount")
    order_level_spread = PMMParameter("order_level_spread")
    order_level_amount = PMMParameter("order_level_amount")
    order_refresh_time = PMMParameter("order_refresh_time")
    order_refresh_tolerance_pct = PMMParameter("order_refresh_tolerance_pct")
    filled_order_delay = PMMParameter("filled_order_delay")
    # inventory_skew_enabled = PMMParameter("inventory_skew_enabled")
    # inventory_target_base_pct = PMMParameter("inventory_target_base_pct")
    # inventory_range_multiplier = PMMParameter("inventory_range_multiplier")
    # hanging_orders_enabled = PMMParameter("hanging_orders_enabled")
    # hanging_orders_cancel_pct = PMMParameter("hanging_orders_cancel_pct")
    # order_optimization_enabled = PMMParameter("order_optimization_enabled")
    # ask_order_optimization_depth = PMMParameter("ask_order_optimization_depth")
    # bid_order_optimization_depth = PMMParameter("bid_order_optimization_depth")
    # add_transaction_costs_to_orders = PMMParameter("add_transaction_costs_to_orders")
    # price_ceiling = PMMParameter("price_ceiling")
    # price_floor = PMMParameter("price_floor")
    # ping_pong_enabled = PMMParameter("ping_pong_enabled")
    # minimum_spread = PMMParameter("minimum_spread")

    def __repr__(self):
        return str(self.__dict__)


class OnTick:
    def __init__(self, mid_price: Decimal, pmm_parameters: PMMParameters):
        self.mid_price = mid_price
        self.pmm_parameters = pmm_parameters

    def __repr__(self):
        return str(self.__dict__)


class CallNotify:
    def __init__(self, msg):
        self.msg = msg
        self.return_value = None
