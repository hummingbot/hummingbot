cdef class Position:
    cdef:
        public str _trading_pair
        public object _position_side
        public object _unrealized_pnl
        public object _entry_price
        public object _amount
        public object _leverage
