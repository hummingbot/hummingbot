# distutils: language=c++

""" Triangular arbitrage model data structure """


#ctypedef enum TradeDirection:
cpdef enum TradeDirection:
    CClockwise = 0,
    Clockwise = 1


cdef str trade_direction_to_str(TradeDirection direction)


cdef class Node():
    cdef:
        str _asset


cdef class Edge():
    cdef:
        int _market_id
        str _trading_pair
        object _trade_type
        object _price
        object _amount
        object _fee


cdef class TriangularArbitrage():
    cdef:
        Node _top
        Node _left
        Node _right
        Edge _left_edge
        Edge _cross_edge
        Edge _right_edge
        TradeDirection direction
        tuple trade_types
        tuple trading_pairs
