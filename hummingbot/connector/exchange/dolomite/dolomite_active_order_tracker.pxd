# distutils: language=c++
cimport numpy as np

cdef class DolomiteActiveOrderTracker:
    cdef dict _active_bids
    cdef dict _active_asks

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message)
