from typing import Iterable, Set, List

from .strategy_task import StrategyTask


cdef class StrategyNode:
    def __init__(self, min_rebalance_size: float):
        self._edges = []
        self._min_rebalance_size = min_rebalance_size

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def asset_name(self) -> str:
        raise NotImplementedError

    @property
    def edges(self) -> List[StrategyNode]:
        return self._edges

    @property
    def total_value(self) -> float:
        return self.c_get_total_value()

    def get_task_for_edge(self, to_node: StrategyNode, value_transfer: float) -> StrategyTask:
        return self.c_get_task_for_edge(to_node, value_transfer)

    def get_tasks(self, edges: List[StrategyNode]) -> List[StrategyTask]:
        return self.c_get_tasks(edges)

    def add_edge_to(self, node: StrategyNode):
        self._edges.append(node)

    cdef double c_get_total_value(self) except? -1:
        raise NotImplementedError

    cdef StrategyTask c_get_task_for_edge(self, StrategyNode to_node, double value_transfer):
        raise NotImplementedError

    cdef list c_get_tasks(self, list edges):
        raise NotImplementedError

    def iter_tree(self, traversed: Set[StrategyNode]) -> Iterable[StrategyNode]:
        if self in traversed:
            return

        traversed.add(self)
        yield self

        for child_node in self._edges:
            yield from child_node.iter_tree(traversed)
