#!/usr/bin/env python

from sqlalchemy.ext.declarative import declarative_base

WingsBase = declarative_base()
SparrowBase = declarative_base()


def get_wings_base():
    from .market_withdraw_rules import MarketWithdrawRules
    return WingsBase


def get_sparrow_base():
    from .asset import Asset
    from .market_data import MarketData
