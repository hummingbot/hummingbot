# distutils: language=c++

from hummingbot.strategy.triangular_arbitrage.model.arbitrage cimport TriangularArbitrage
from hummingbot.strategy.triangular_arbitrage.optimizer.optimizer cimport Optimizer


cdef class TriangularArbitrageCalculator():
    cdef:
        str _name
        str _target_node
        str _left_node
        str _right_node
        str _primary_market
        str _secondary_market
        str _tertiary_market
        str _primary_trading_pair
        str _secondary_trading_pair
        str _tertiary_trading_pair
        object _min_profitability
        TriangularArbitrage _ccw_arb
        TriangularArbitrage _cw_arb
        Optimizer _optimizer
        object _preprocessor
        object _fees

    cdef object c_calculate_arbitrage(self, list market_pairs)
    cdef object c_check_profit(self, TriangularArbitrage arb, list market_pairs)

