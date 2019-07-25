#!/usr/bin/env python

from collections import namedtuple
from enum import Enum


class AssetType(Enum):
    BASE_CURRENCY = 1
    QUOTE_CURRENCY = 2


class MarketConfig(namedtuple("_MarketConfig", "buy_fees_asset,"
                                               "buy_fees_amount,"
                                               "sell_fees_asset,"
                                               "sell_fees_amount,")):
    buy_fees_asset: AssetType
    buy_fees_amount: float
    sell_fees_asset: AssetType
    sell_fees_amount: float

    @classmethod
    def default_config(cls) -> "MarketConfig":
        return MarketConfig(AssetType.BASE_CURRENCY, 0.0, AssetType.QUOTE_CURRENCY, 0.0)

    @classmethod
    def create_config(cls, trading_fee: float):
        return MarketConfig(AssetType.BASE_CURRENCY, trading_fee, AssetType.QUOTE_CURRENCY, trading_fee)
