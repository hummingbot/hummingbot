cdef class StrategyGroup:
    cdef:
        list _nodes
        str _name

    cdef double c_get_total_value(self) except? -1
    cdef list c_get_tasks(self, StrategyGroup to_group)
