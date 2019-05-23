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
    this->obj = other.obj;
    Py_XINCREF(this->obj);
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