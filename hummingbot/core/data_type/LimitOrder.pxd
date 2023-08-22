# distutils: language=c++

from libcpp cimport bool as cppbool
from libcpp.string cimport string

cdef extern from "../cpp/LimitOrder.h":
    ctypedef struct PyObject

    cdef cppclass LimitOrder:
        LimitOrder()
        LimitOrder(string clientOrderID,
                   string tradingPair,
                   cppbool isBuy,
                   string baseCurrency,
                   string quoteCurrency,
                   PyObject *price,
                   PyObject *quantity)
        LimitOrder(string clientOrderID,
                   string tradingPair,
                   cppbool isBuy,
                   string baseCurrency,
                   string quoteCurrency,
                   PyObject *price,
                   PyObject *quantity,
                   PyObject *filledQuantity,
                   long long creationTimestamp,
                   short int status,
                   string position)
        LimitOrder(const LimitOrder &other)
        LimitOrder &operator=(const LimitOrder &other)
        string getClientOrderID()
        string getTradingPair()
        cppbool getIsBuy()
        string getBaseCurrency()
        string getQuoteCurrency()
        PyObject *getPrice()
        PyObject *getQuantity()
        PyObject *getFilledQuantity()
        long long getCreationTimestamp()
        short int getStatus()
        string getPosition()
