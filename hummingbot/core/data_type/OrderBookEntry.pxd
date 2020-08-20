# distutils: language=c++

from libc.stdint cimport int64_t
from libcpp.set cimport set

cdef extern from "../cpp/OrderBookEntry.h":
    cdef cppclass OrderBookEntry:
        OrderBookEntry()
        OrderBookEntry(double price, double amount, int64_t updateId)
        OrderBookEntry(const OrderBookEntry &other)
        OrderBookEntry &operator=(const OrderBookEntry &other)
        double getPrice() const
        double getAmount() const
        int64_t getUpdateId() const

    void truncateOverlapEntries(set[OrderBookEntry] &bid_book, set[OrderBookEntry] &ask_book, const bint &dex)
