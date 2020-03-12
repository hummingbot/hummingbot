#include "LimitOrder.h"

LimitOrder::LimitOrder() {
    this->clientOrderID = "";
    this->tradingPair = "";
    this->isBuy = false;
    this->baseCurrency = "";
    this->quoteCurrency = "";
    this->price = NULL;
    this->quantity = NULL;
}

LimitOrder::LimitOrder(std::string clientOrderID,
                       std::string tradingPair,
                       bool isBuy,
                       std::string baseCurrency,
                       std::string quoteCurrency,
                       PyObject *price,
                       PyObject *quantity) {
    this->clientOrderID = clientOrderID;
    this->tradingPair = tradingPair;
    this->isBuy = isBuy;
    this->baseCurrency = baseCurrency;
    this->quoteCurrency = quoteCurrency;
    this->price = price;
    this->quantity = quantity;
    Py_XINCREF(price);
    Py_XINCREF(quantity);
}

LimitOrder::LimitOrder(const LimitOrder &other) {
    this->clientOrderID = other.clientOrderID;
    this->tradingPair = other.tradingPair;
    this->isBuy = other.isBuy;
    this->baseCurrency = other.baseCurrency;
    this->quoteCurrency = other.quoteCurrency;
    this->price = other.price;
    this->quantity = other.quantity;
    Py_XINCREF(this->price);
    Py_XINCREF(this->quantity);
}

LimitOrder::~LimitOrder() {
    Py_XDECREF(this->price);
    Py_XDECREF(this->quantity);
    this->price = NULL;
    this->quantity = NULL;
}

LimitOrder &LimitOrder::operator=(const LimitOrder &other) {
    this->clientOrderID = other.clientOrderID;
    this->tradingPair = other.tradingPair;
    this->isBuy = other.isBuy;
    this->baseCurrency = other.baseCurrency;
    this->quoteCurrency = other.quoteCurrency;
    this->price = other.price;
    this->quantity = other.quantity;
    Py_XINCREF(this->price);
    Py_XINCREF(this->quantity);

    return *this;
}

bool operator<(LimitOrder const &a, LimitOrder const &b) {
    return (bool)(PyObject_RichCompareBool(a.price, b.price, Py_LT));
}

std::string LimitOrder::getClientOrderID() const {
    return this->clientOrderID;
}

std::string LimitOrder::getTradingPair() const {
    return this->tradingPair;
}

bool LimitOrder::getIsBuy() const {
    return this->isBuy;
}

std::string LimitOrder::getBaseCurrency() const {
    return this->baseCurrency;
}

std::string LimitOrder::getQuoteCurrency() const {
    return this->quoteCurrency;
}

PyObject *LimitOrder::getPrice() const {
    return this->price;
}

PyObject *LimitOrder::getQuantity() const {
    return this->quantity;
}
