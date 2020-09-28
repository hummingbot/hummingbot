# distutils: language=c++

from libcpp.string cimport string

cdef extern from "../cpp/OrderExpirationEntry.h":
    cdef cppclass OrderExpirationEntry:
        OrderExpirationEntry()
        OrderExpirationEntry(string trading_pair,
                             string order_id,
                             double timestamp,
                             double expiration)
        OrderExpirationEntry(const OrderExpirationEntry &other)
        OrderExpirationEntry &operator=(const OrderExpirationEntry &other)
        string getClientOrderID()
        string getTradingPair()
        double getTimestamp()
        double getExpiration()
        double getExpirationTimestamp()
