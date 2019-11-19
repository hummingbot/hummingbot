#ifndef _ORDER_EXPIRATION_ENTRY_H
#define _ORDER_EXPIRATION_ENTRY_H

#include <string>
#include <set>
#include <iterator>
#include <Python.h>

class OrderExpirationEntry {
    std::string tradingPair;
    std::string orderId;
    double timestamp;
    double expiration_timestamp;

    public:
        OrderExpirationEntry();
        OrderExpirationEntry(std::string tradingPair, std::string orderId, double timestamp, double expiration_timestamp);
        OrderExpirationEntry(const OrderExpirationEntry &other);
        OrderExpirationEntry &operator=(const OrderExpirationEntry &other);
        friend bool operator<(OrderExpirationEntry const &a, OrderExpirationEntry const &b);
        std::string getTradingPair() const;
        std::string getClientOrderID() const;
        double getTimestamp() const;
        double getExpirationTimestamp() const;
};

#endif
