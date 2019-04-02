from .strategy_group cimport StrategyGroup
from .strategy_node cimport StrategyNode


cdef class StrategyGraph:
    cdef:
        dict _groups_map
        dict _nodes_map

    cdef c_connect_nodes(self, StrategyNode node1, StrategyNode node2)
    cdef StrategyGroup c_get_group(self, str group_name)
    cdef StrategyNode c_get_node(self, str node_name)
    cdef double c_get_total_portfolio_value(self)