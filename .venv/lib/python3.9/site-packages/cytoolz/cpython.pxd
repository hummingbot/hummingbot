""" Additional bindings to Python's C-API.

These differ from Cython's bindings in ``cpython``.
"""
from cpython.ref cimport PyObject

cdef extern from "Python.h":
    PyObject* PtrIter_Next "PyIter_Next"(object o)
    PyObject* PtrObject_Call "PyObject_Call"(object callable_object, object args, object kw)
    PyObject* PtrObject_GetItem "PyObject_GetItem"(object o, object key)
    int PyDict_Next_Compat "PyDict_Next"(object p, Py_ssize_t *ppos, PyObject* *pkey, PyObject* *pvalue) except -1
