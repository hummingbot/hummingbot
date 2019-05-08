from wings.network_iterator cimport NetworkIterator


cdef class WalletBase(NetworkIterator):
    cdef double c_get_balance(self, str asset_name) except? -1
    cdef object c_get_raw_balance(self, str asset_name)
    cdef str c_send(self, str address, str currency, double amount)
