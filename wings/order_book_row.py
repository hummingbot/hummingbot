#!/usr/bin/env python

from collections import namedtuple


class OrderBookRow(namedtuple("_OrderBookRow", "price, amount, update_id")):
    price: float
    amount: float
    update_id: int

