from libc.stdint cimport int64_t


cdef class TradingIntensityIndicator():
    cdef:
        double _alpha
        double _kappa
        list _trades
        object _bids_df
        object _asks_df
        int _sampling_length
        int _samples_length

    cdef c_simulate_execution(self, bids_df, asks_df)
    cdef c_estimate_intensity(self)
