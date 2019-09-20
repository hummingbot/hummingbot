from .pure_market_making_v2 cimport PureMarketMakingStrategyV2
from .data_types import (ORDER_PROPOSAL_ACTION_CREATE_ORDERS,
                         OrdersProposal)

cdef class PassThroughFilterDelegate(OrderFilterDelegate):

    def __init__(self):
        super().__init__()

    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info,
                                               list active_orders) except? True:
        return True

    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         list active_orders,
                                         object orders_proposal):
        cdef:
            int64_t actions = orders_proposal.actions

        current_timestamp = strategy._current_timestamp

        # If the current timestamp is greater than the timestamp to place order do not modify order proposal
        if current_timestamp > self._order_placing_timestamp:
            return orders_proposal

        # If the current timestamp is less than the timestamp to place order modify order proposal to NOT place orders
        else:
            # If the proposal is trying to create orders
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
