#!/usr/bin/env python

from collections import namedtuple
from decimal import Decimal


class OrderBookRow(namedtuple("_OrderBookRow", "price, amount, update_id")):
    price: float
    amount: float
    update_id: int


class ClientOrderBookRow(namedtuple("_OrderBookRow", "price, amount, update_id")):
    price: Decimal
    amount: Decimal
    update_id: int


