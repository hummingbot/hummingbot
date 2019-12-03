# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderExpirationEntry.cpp

from libcpp.string cimport string
import pandas as pd
from typing import List

cdef class OrderExpirationEntry:
    @classmethod
    def to_pandas(cls, order_expiration_entries: List[OrderExpirationEntry]) -> pd.DataFrame:
        cdef:
            list columns = ["trading_pair", "order_id", "timestamp", "expiration", "expiration_time"]
            list data = [[
                expiration_entry.trading_pair,
                expiration_entry.order_id,
                expiration_entry.timestamp,
                expiration_entry.expiration,
                expiration_entry.expiration_time
            ] for expiration_entry in order_expiration_entries]

        return pd.DataFrame(data=data, columns=columns)

    def __init__(self,
                 trading_pair: str,
                 order_id: str,
                 timestamp: float,
                 expiration_ts: float
                 ):
        cdef:
            string cpp_trading_pair = trading_pair.encode("utf8")
            string cpp_order_id = order_id.encode("utf8")
            double cpp_timestamp = timestamp
            double cpp_expiration_ts = expiration_ts

        self._cpp_order_expiration_entry = CPPOrderExpirationEntry(cpp_trading_pair,
                                                                   cpp_order_id,
                                                                   cpp_timestamp,
                                                                   cpp_expiration_ts)

    @property
    def trading_pair(self) -> str:
        cdef:
            string cpp_trading_pair = self._cpp_order_expiration_entry.getTradingPair()
            str retval = cpp_trading_pair.decode("utf8")
        return retval

    @property
    def order_id(self) -> str:
        cdef:
            string cpp_client_order_id = self._cpp_order_expiration_entry.getClientOrderID()
            str retval = cpp_client_order_id.decode("utf8")
        return retval

    @property
    def timestamp(self) -> float:
        return self._cpp_order_expiration_entry.getTimestamp()

    @property
    def expiration_timestamp(self) -> float:
        return self._cpp_order_expiration_entry.getExpirationTimestamp()

    def __repr__(self) -> str:
        return f"OrderExpirationEntry('{self.trading_pair}', '{self.order_id}', {self.timestamp}, '{self.expiration_timestamp}')"


cdef OrderExpirationEntry c_create_order_expiration_from_cpp_order_expiration(const CPPOrderExpirationEntry cpp_order_expiration_entry):
    cdef OrderExpirationEntry retval = OrderExpirationEntry.__new__(OrderExpirationEntry)
    retval._cpp_order_expiration_entry = cpp_order_expiration_entry
    return retval
