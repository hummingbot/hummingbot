#include "OrderExpirationEntry.h"
#include <iostream>

OrderExpirationEntry::OrderExpirationEntry() {
    this->symbol = "";
    this->orderId = "";
    this->timestamp = 0;
    this->expiration_timestamp = 0;
}

OrderExpirationEntry::OrderExpirationEntry(std::string symbol,
                                           std::string orderId,
                                           double timestamp,
                                           double expiration_timestamp) {
    this->symbol = symbol;
    this->orderId = orderId;
    this->timestamp = timestamp;
    this->expiration_timestamp = expiration_timestamp;
}

OrderExpirationEntry::OrderExpirationEntry(const OrderExpirationEntry &other) {
    this->symbol = other.symbol;
    this->orderId = other.orderId;
    this->timestamp = other.timestamp;
    this->expiration_timestamp = other.expiration_timestamp;
}

OrderExpirationEntry &OrderExpirationEntry::operator=(const OrderExpirationEntry &other) {
    this->symbol = other.symbol;
    this->orderId = other.orderId;
    this->timestamp = other.timestamp;
    this->expiration_timestamp = other.expiration_timestamp;
    return *this;
}

bool operator<(OrderExpirationEntry const &a, OrderExpirationEntry const &b) {
    if(a.expiration_timestamp == b.expiration_timestamp){
        return a.orderId < b.orderId;
    }
    else{
        return a.expiration_timestamp < b.expiration_timestamp;
    }
}

std::string OrderExpirationEntry::getSymbol() const {
    return this->symbol;
}

std::string OrderExpirationEntry::getClientOrderID() const {
    return this->orderId;
}

double OrderExpirationEntry::getTimestamp() const {
    return this->timestamp;
}

double OrderExpirationEntry::getExpirationTimestamp() const {
    return this->expiration_timestamp;
}
