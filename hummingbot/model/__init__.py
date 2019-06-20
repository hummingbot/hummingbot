#!/usr/bin/env python

from sqlalchemy.ext.declarative import declarative_base

HummingbotBase = declarative_base()


def get_declarative_base():
    from .market_state import MarketState
    from .metadata import Metadata
    from .order import Order
    from .order_status import OrderStatus
    from .trade_fill import TradeFill
    return HummingbotBase
