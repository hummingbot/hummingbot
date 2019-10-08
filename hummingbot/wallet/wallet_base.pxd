from hummingbot.core.network_iterator cimport NetworkIterator
from decimal import Decimal


cdef class WalletBase(NetworkIterator):
    cdef object c_get_balance(self, str asset_name)
    cdef object c_get_raw_balance(self, str asset_name)
    cdef str c_send(self, str address, str currency, object amount)
