#include "LimitOrder.h"

LimitOrder::LimitOrder() {
    this->clientOrderID = "";
    this->price = NULL;
    this->quantity = NULL;
    this->spread = NULL;
}

LimitOrder::LimitOrder(std::string clientOrderID,
                       PyObject *price,
                       PyObject *quantity,
                       PyObject *spread) {
    this->clientOrderID = clientOrderID;
    this->price = price;
    this->quantity = quantity;
    this->spread = spread;
    Py_XINCREF(price);
    Py_XINCREF(quantity);
    Py_XINCREF(spread);
}

LimitOrder::LimitOrder(const LimitOrder &other) {
    this->clientOrderID = other.clientOrderID;
    this->price = other.price;
    this->quantity = other.quantity;
    this->spread = other.spread;
    Py_XINCREF(this->price);
    Py_XINCREF(this->quantity);
    Py_XINCREF(this->spread);
}

LimitOrder::~LimitOrder() {
    Py_XDECREF(this->price);
    Py_XDECREF(this->quantity);
    Py_XDECREF(this->spread);
    this->price = NULL;
    this->quantity = NULL;
    this->spread = NULL;
}

LimitOrder &LimitOrder::operator=(const LimitOrder &other) {
    this->clientOrderID = other.clientOrderID;
    this->price = other.price;
    this->quantity = other.quantity;
    this->spread = other.spread;
    Py_XINCREF(this->price);
    Py_XINCREF(this->quantity);
    Py_XINCREF(this->spread);

    return *this;
}

bool operator<(LimitOrder const &a, LimitOrder const &b) {
    return (bool)(PyObject_RichCompareBool(a.price, b.price, Py_LT));
}

std::string LimitOrder::getClientOrderID() const {
    return this->clientOrderID;
}

PyObject *LimitOrder::getPrice() const {
    return this->price;
}

PyObject *LimitOrder::getQuantity() const {
    return this->quantity;
}

PyObject *LimitOrder::getSpread() const {
    return this->spread;
}
