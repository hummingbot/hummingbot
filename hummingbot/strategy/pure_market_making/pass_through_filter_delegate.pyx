from .pure_market_making_v2 cimport PureMarketMakingStrategyV2
from .data_types import (ORDER_PROPOSAL_ACTION_CREATE_ORDERS,
                         OrdersProposal)
from hummingbot.logger import HummingbotLogger
import logging
s_logger = None

cdef class PassThroughFilterDelegate(OrderFilterDelegate):

    def __init__(self, order_placing_timestamp: float):
        super().__init__()
        self._order_placing_timestamp = order_placing_timestamp

    @property
    def order_placing_timestamp(self) -> float:
        return self._order_placing_timestamp

    @order_placing_timestamp.setter
    def order_placing_timestamp(self, double order_placing_timestamp):
        self.logger().info(f"order placing timestamp is {order_placing_timestamp}")
        self._order_placing_timestamp = order_placing_timestamp

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info,
                                               list active_orders) except? True:
        return True

    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         object orders_proposal):
        cdef:
            int64_t actions = orders_proposal.actions

        current_timestamp = strategy._current_timestamp

        # If the current timestamp is greater than the timestamp to place order do not modify order proposal
        if current_timestamp > self._order_placing_timestamp:
            return orders_proposal

        # If the current timestamp is less than the timestamp to place order modify order proposal to NOT place orders
        else:
            if actions & ORDER_PROPOSAL_ACTION_CREATE_ORDERS:
                # set actions to not create orders by masking the Order creation bit
                # Refer datatypes.py
                actions = actions & (1 << 1)

            return OrdersProposal(actions,
                                  orders_proposal.buy_order_type,
                                  orders_proposal.buy_order_prices,
                                  orders_proposal.buy_order_sizes,
                                  orders_proposal.sell_order_type,
                                  orders_proposal.sell_order_prices,
                                  orders_proposal.sell_order_sizes,
                                  orders_proposal.cancel_order_ids)