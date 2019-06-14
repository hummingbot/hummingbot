#!/usr/bin/env python

from sqlalchemy.ext.declarative import declarative_base

HummingbotBase = declarative_base()


def get_declarative_base():
    from .trade_fill import TradeFill
    from .order import Order
    from .order_status import OrderStatus
    return HummingbotBase
