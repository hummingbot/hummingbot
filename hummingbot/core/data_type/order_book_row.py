#!/usr/bin/env python

from collections import namedtuple
from decimal import Decimal


class OrderBookRow(namedtuple("_OrderBookRow", "price, amount, update_id")):
    """
    Used to apply changes to OrderBook. OrderBook classes uses float internally for better performance over Decimal.
    """
    price: float
    amount: float
    update_id: int


class ClientOrderBookRow(namedtuple("_OrderBookRow", "price, amount, update_id")):
    """
    Used in market classes where OrderBook values are converted to Decimal.
    """
    price: Decimal
    amount: Decimal
    update_id: int
