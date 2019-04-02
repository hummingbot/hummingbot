from .strategy_task cimport StrategyTask


cdef class StrategyNode:
    cdef:
        list _edges
        double _min_rebalance_size

    cdef double c_get_total_value(self) except? -1
    cdef StrategyTask c_get_task_for_edge(self, StrategyNode to_node, double value_transfer)
    cdef list c_get_tasks(self, list edges)
