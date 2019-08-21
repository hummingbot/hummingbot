#!/usr/bin/env python

from collections import (namedtuple, Mapping)

# Support for namedtuple defaults for pre v3.7.0
def namedtuple_with_defaults(typename, field_names, default_values=()):
    T = namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T

class OrderBookRow(namedtuple_with_defaults("_OrderBookRow", "price, amount, update_id, order_count", { "order_count": 1 })):
    price: float
    amount: float
    update_id: int
    order_count: int

