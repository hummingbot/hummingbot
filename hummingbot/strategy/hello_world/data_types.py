#!/usr/bin/env python

from typing import (
    NamedTuple,
    List
)

from decimal import Decimal

from hummingbot.core.event.events import OrderType
from hummingbot.market.market_base import MarketBase

class MarketInfo(NamedTuple):
    market: MarketBase
    symbol: str
    base_currency: str
    quote_currency: str
