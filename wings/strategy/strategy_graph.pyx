from typing import (
    Dict,
    Iterable,
    Optional
)

from .strategy_group import StrategyGroup
from .strategy_group cimport StrategyGroup
from .strategy_node import StrategyNode
from .strategy_node cimport StrategyNode


cdef class StrategyGraph:
    def __init__(self):
        self._groups_map = {}
        self._nodes_map = {}

    @property
    def strategy_groups(self) -> Dict[str, StrategyGroup]:
        return self._groups_map

    def add_groups(self, groups: Iterable[StrategyGroup]):
        for group in groups:
            self._groups_map[group.name] = group
            self.add_nodes(group.nodes)

    def add_nodes(self, nodes: Iterable[StrategyNode]):
        for node in nodes:
            self._nodes_map[node.name] = node

    def get_group(self, str group_name) -> Optional[StrategyGroup]:
        return self.c_get_group(group_name)

    def get_node(self, str node_name) -> Optional[StrategyNode]:
        return self.c_get_node(node_name)

    cdef c_connect_nodes(self, StrategyNode node1, StrategyNode node2):
        node1.add_edge_to(node2)
        node2.add_edge_to(node1)

    cdef StrategyGroup c_get_group(self, str group_name):
        return self._groups_map.get(group_name)

    cdef StrategyNode c_get_node(self, str node_name):
        return self._nodes_map.get(node_name)

    cdef double c_get_total_portfolio_value(self):
        cdef:
            StrategyNode typed_node = None
            double retval = 0.0

        for node in self._nodes_map.values():
            typed_node = node
            retval += typed_node.c_get_total_value()

        return retval
