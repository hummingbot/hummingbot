# distutils: language=c++
cimport numpy as np

cdef class BlocktaneActiveOrderTracker:
    cdef dict _active_bids
    cdef dict _active_asks

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message)
