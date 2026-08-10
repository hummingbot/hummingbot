#ifndef _LIMIT_ORDER_H
#define _LIMIT_ORDER_H

#include <string>
#include <Python.h>

class LimitOrder {
    std::string clientOrderID;
    std::string tradingPair;
    bool isBuy;
    std::string baseCurrency;
    std::string quoteCurrency;
    PyObject *price;
    PyObject *quantity;
    PyObject *filledQuantity;
    long creationTimestamp;
    short int status;
    std::string position;

    public:
        LimitOrder();
        LimitOrder(std::string clientOrderID,
                   std::string tradingPair,
                   bool isBuy,
                   std::string baseCurrency,
                   std::string quoteCurrency,
                   PyObject *price,
                   PyObject *quantity);
        LimitOrder(std::string clientOrderID,
                   std::string tradingPair,
                   bool isBuy,
                   std::string baseCurrency,
                   std::string quoteCurrency,
                   PyObject *price,
                   PyObject *quantity,
                   PyObject *filledQuantity,
                   long creationTimestamp,
                   short int status,
                   std::string position);
        ~LimitOrder();
        LimitOrder(const LimitOrder &other);
        LimitOrder &operator=(const LimitOrder &other);
        friend bool operator<(LimitOrder const &a, LimitOrder const &b);

        std::string getClientOrderID() const;
        std::string getTradingPair() const;
        bool getIsBuy() const;
        std::string getBaseCurrency() const;
        std::string getQuoteCurrency() const;
        PyObject *getPrice() const;
        PyObject *getQuantity() const;
        PyObject *getFilledQuantity() const;
        long getCreationTimestamp() const;
        short int getStatus() const;
        std::string getPosition() const;
};

#endif
