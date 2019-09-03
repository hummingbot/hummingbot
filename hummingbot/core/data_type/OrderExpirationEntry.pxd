# distutils: language=c++

from libcpp.string cimport string

cdef extern from "../cpp/OrderExpirationEntry.h":
    cdef cppclass OrderExpirationEntry:
        OrderExpirationEntry()
        OrderExpirationEntry(string symbol,
                             string order_id,
                             double timestamp,
                             double expiration)
        OrderExpirationEntry(const OrderExpirationEntry &other)
        OrderExpirationEntry &operator=(const OrderExpirationEntry &other)
        string getClientOrderID();
        string getSymbol();
        double getTimestamp();
        double getExpiration();
        double getExpirationTimestamp();

