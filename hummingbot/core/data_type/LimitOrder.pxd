# distutils: language=c++

from libcpp cimport bool
from libcpp.string cimport string

cdef extern from "../cpp/LimitOrder.h":
    ctypedef struct PyObject

    cdef cppclass LimitOrder:
        LimitOrder()
        LimitOrder(string clientOrderID,
                   string tradingPair,
                   bool isBuy,
                   string baseCurrency,
                   string quoteCurrency,
                   PyObject *price,
                   PyObject *quantity)
        LimitOrder(const LimitOrder &other)
        LimitOrder &operator=(const LimitOrder &other)
        string getClientOrderID();
        string getTradingPair();
        bool getIsBuy();
        string getBaseCurrency();
        string getQuoteCurrency();
        PyObject *getPrice();
        PyObject *getQuantity();
