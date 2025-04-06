#include "LimitOrder.h"

LimitOrder::LimitOrder() {
    this->clientOrderID = "";
    this->tradingPair = "";
    this->isBuy = false;
    this->baseCurrency = "";
    this->quoteCurrency = "";
    this->price = NULL;
    this->quantity = NULL;
    this->filledQuantity = NULL;
    this->creationTimestamp = 0.0;
    this->status = 0;
    this->position = "NIL";
}

LimitOrder::LimitOrder(std::string clientOrderID,
                       std::string tradingPair,
                       bool isBuy,
                       std::string baseCurrency,
                       std::string quoteCurrency,
                       PyObject *price,
                       PyObject *quantity
                       ) {
    this->clientOrderID = clientOrderID;
    this->tradingPair = tradingPair;
    this->isBuy = isBuy;
    this->baseCurrency = baseCurrency;
    this->quoteCurrency = quoteCurrency;
    this->price = price;
    this->quantity = quantity;
    this->filledQuantity = NULL;
    this->creationTimestamp = 0.0;
    this->status = 0;
    this->position = "NIL";
    Py_XINCREF(price);
    Py_XINCREF(quantity);
}

LimitOrder::LimitOrder(std::string clientOrderID,
                       std::string tradingPair,
                       bool isBuy,
                       std::string baseCurrency,
                       std::string quoteCurrency,
                       PyObject *price,
                       PyObject *quantity,
                       PyObject *filledQuantity,
                       long creationTimestamp,
                       short int status,
                       std::string position
                       ) {
    this->clientOrderID = clientOrderID;
    this->tradingPair = tradingPair;
    this->isBuy = isBuy;
    this->baseCurrency = baseCurrency;
    this->quoteCurrency = quoteCurrency;
    this->price = price;
    this->quantity = quantity;
    this->filledQuantity = filledQuantity;
    this->creationTimestamp = creationTimestamp;
    this->status = status;
    this->position = position;
    Py_XINCREF(price);
    Py_XINCREF(quantity);
    Py_XINCREF(filledQuantity);
}

LimitOrder::LimitOrder(const LimitOrder &other) {
    this->clientOrderID = other.clientOrderID;
    this->tradingPair = other.tradingPair;
    this->isBuy = other.isBuy;
    this->baseCurrency = other.baseCurrency;
    this->quoteCurrency = other.quoteCurrency;
    this->price = other.price;
    this->quantity = other.quantity;
    this->filledQuantity = other.filledQuantity;
    this->creationTimestamp = other.creationTimestamp;
    this->status = other.status;
    this->position = other.position;
    Py_XINCREF(this->price);
    Py_XINCREF(this->quantity);
    Py_XINCREF(this->filledQuantity);
}

LimitOrder::~LimitOrder() {
    Py_XDECREF(this->price);
    Py_XDECREF(this->quantity);
    Py_XDECREF(this->filledQuantity);
    this->price = NULL;
    this->quantity = NULL;
    this->filledQuantity = NULL;
}

LimitOrder &LimitOrder::operator=(const LimitOrder &other) {
    this->clientOrderID = other.clientOrderID;
    this->tradingPair = other.tradingPair;
    this->isBuy = other.isBuy;
    this->baseCurrency = other.baseCurrency;
    this->quoteCurrency = other.quoteCurrency;
    this->price = other.price;
    this->quantity = other.quantity;
    this->filledQuantity = other.filledQuantity;
    this->creationTimestamp = other.creationTimestamp;
    this->status = other.status;
    this->position = other.position;
    Py_XINCREF(this->price);
    Py_XINCREF(this->quantity);
    Py_XINCREF(this->filledQuantity);

    return *this;
}

bool operator<(LimitOrder const &a, LimitOrder const &b) {
    if ((bool)(PyObject_RichCompareBool(a.price, b.price, Py_EQ))) {
        // return (bool)(PyObject_RichCompareBool(a.quantity, b.quantity, Py_LT));
        return (bool)(a.clientOrderID < b.clientOrderID);
    } else {
        return (bool)(PyObject_RichCompareBool(a.price, b.price, Py_LT));
    }
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

PyObject *LimitOrder::getFilledQuantity() const {
    return this->filledQuantity;
}

long LimitOrder::getCreationTimestamp() const{
    return this->creationTimestamp;
}

short int LimitOrder::getStatus() const{
    return this->status;
}

std::string LimitOrder::getPosition() const{
    return this->position;
}
