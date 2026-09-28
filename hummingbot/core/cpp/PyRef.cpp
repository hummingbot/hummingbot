#include "PyRef.h"
#include <iostream>

PyRef::PyRef() {
    this->obj = NULL;
}

PyRef::PyRef(PyObject *obj) {
    this->obj = obj;
    Py_XINCREF(obj);
}

PyRef::PyRef(const PyRef &other) {
    this->obj = other.obj;
    Py_XINCREF(this->obj);
}

PyRef::~PyRef() {
    Py_XDECREF(this->obj);
}

PyRef &PyRef::operator=(const PyRef &other) {
    if (this != &other) {
        // Release the previous reference before rebinding: Cython-generated loops
        // (e.g. "for pyref in listeners:" in pubsub) assign into a single PyRef
        // variable once per iteration, so skipping this DECREF leaks one reference
        // per element per iteration.
        Py_XDECREF(this->obj);
        this->obj = other.obj;
        Py_XINCREF(this->obj);
    }
    return *this;
}

bool PyRef::operator==(const PyRef &other) const {
    return this->obj == other.obj;
}

PyObject *PyRef::get() const {
    return this->obj;
}

namespace std {
    size_t hash<PyRef>::operator()(const PyRef &x) const {
        return PyObject_Hash(x.get());
    }
}
