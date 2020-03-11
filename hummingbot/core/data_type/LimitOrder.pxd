# distutils: language=c++

from libcpp cimport bool
from libcpp.string cimport string

cdef extern from "../cpp/LimitOrder.h":
    ctypedef struct PyObject

    cdef cppclass LimitOrder:
        LimitOrder()
        LimitOrder(string clientOrderID,
                   PyObject *price,
                   PyObject *quantity,
                   PyObject *spread)
        LimitOrder(const LimitOrder &other)
        LimitOrder &operator=(const LimitOrder &other)
        string getClientOrderID()
        PyObject *getPrice()
        PyObject *getQuantity()
        PyObject *getSpread()
