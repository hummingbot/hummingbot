# distutils: language=c++
cimport numpy as np

cdef class IDEXActiveOrderTracker:
    cdef dict _active_bids
    cdef dict _active_asks
    cdef dict _base_asset
    cdef dict _quote_asset
    cdef double _latest_snapshot_timestamp
    cdef dict _order_hash_price_map
    cdef object _received_trade_ids
    cdef set _order_hashes_to_delete
    cdef list _bid_heap
    cdef list _ask_heap

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message)
    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message)
    cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message)
    