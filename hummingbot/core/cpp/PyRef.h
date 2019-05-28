#ifndef _PYREF_H
#define _PYREF_H

#include <Python.h>
#include <iostream>
#include <functional>

class PyRef {
    PyObject *obj;

    public:
        PyRef();
        PyRef(PyObject *obj);
        PyRef(const PyRef &other);
        PyRef &operator=(const PyRef &other);
        bool operator==(const PyRef &other) const;
        ~PyRef();
        PyObject *get() const;
};


namespace std {
    template <>
    struct hash<PyRef>
    {
        size_t operator()(const PyRef &x) const;
    };
}

#endif