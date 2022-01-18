# distutils: language=c++
cimport numpy as np


cdef class GateIoActiveOrderTracker:
    cdef dict _active_bids
    cdef dict _active_asks

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message)
    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message)
    # This method doesn't seem to be used anywhere at all
    # cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message)
