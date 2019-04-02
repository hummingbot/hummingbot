from typing import List

from wings.strategy.strategy_node import StrategyNode
from wings.strategy.strategy_node cimport StrategyNode
from wings.strategy.strategy_task import StrategyTask


cdef class StrategyGroup:
    def __init__(self, name: str, nodes: List[StrategyNode]):
        self._nodes = nodes.copy()
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def nodes(self) -> List[StrategyNode]:
        return self._nodes.copy()

    @property
    def total_value(self) -> float:
        return self.c_get_total_value()

    def get_tasks(self, StrategyGroup to_group) -> List[StrategyTask]:
        return self.c_get_tasks(to_group)

    cdef double c_get_total_value(self) except? -1:
        cdef:
            double retval = 0
            StrategyNode typed_node = None

        for node in self._nodes:
            typed_node = node
            retval += typed_node.c_get_total_value()

        return retval

    cdef list c_get_tasks(self, StrategyGroup to_group):
        cdef:
            list retval = []
            set group_nodes
            set edge_set
            StrategyNode typed_node = None
        for node in self._nodes:
            typed_node = node
            group_nodes = set(to_group._nodes)
            edge_set = set(typed_node._edges)
            retval.extend(typed_node.c_get_tasks(list(group_nodes.intersection(edge_set))))
        return retval
