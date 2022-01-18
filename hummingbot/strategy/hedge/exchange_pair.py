#!/usr/bin/env python

from typing import NamedTuple
from hummingbot.connector.exchange_base import ExchangeBase


class ExchangePairTuple(NamedTuple):
    maker: ExchangeBase
    taker: ExchangeBase
