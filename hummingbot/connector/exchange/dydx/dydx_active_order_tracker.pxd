# distutils: language=c++
cimport numpy as np

cdef class DydxActiveOrderTracker:
    cdef object _token_config
    cdef dict _active_bids_by_id
    cdef dict _active_asks_by_id
    cdef dict _active_bids_by_price
    cdef dict _active_asks_by_price
    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message)
    cdef tuple c_convert_diff_message_to_np_arrays(self, object message)
