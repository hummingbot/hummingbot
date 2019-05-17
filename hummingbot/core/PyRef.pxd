# distutils: language=c++

cdef extern from "cpp/PyRef.h":
    ctypedef struct PyObject

    cdef cppclass PyRef:
        PyRef()
        PyRef(PyObject *obj)
        PyRef(const PyRef &other)
        PyRef &operator=(const PyRef &other)
        bint operator==(const PyRef &other) const
        PyObject *get() const
