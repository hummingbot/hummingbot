#!/usr/bin/env python

from collections import namedtuple
from enum import Enum
from typing import (
    Dict,
    List,
)

from hummingsim.model.sql_connection_manager import SQLConnectionManager
from hummingsim.model.market_withdraw_rules import MarketWithdrawRules


class AssetType(Enum):
    BASE_CURRENCY = 1
    QUOTE_CURRENCY = 2


class MarketConfig(namedtuple("_MarketConfig", "buy_fees_asset,"
                                               "buy_fees_amount,"
                                               "sell_fees_asset,"
                                               "sell_fees_amount,"
                                               "withdrawal_fees_amounts")):
    buy_fees_asset: AssetType
    buy_fees_amount: float
    sell_fees_asset: AssetType
    sell_fees_amount: float
    withdrawal_fees_amounts: Dict[str, float]

    @classmethod
    def default_config(cls) -> "MarketConfig":
        return MarketConfig(AssetType.BASE_CURRENCY, 0.0, AssetType.QUOTE_CURRENCY, 0.0, {})

    @classmethod
    def create_binance_backtest_config(cls, sql: SQLConnectionManager, trading_fee: float):
        withdraw_fee_amounts: Dict[str, float] = {}
        with sql.begin() as session:
            rules: List[MarketWithdrawRules] = session.query(MarketWithdrawRules)\
                .filter(MarketWithdrawRules.exchange_name == "Binance")\
                .all()
            for rule in rules:
                withdraw_fee_amounts[rule.asset_name] = float(rule.withdraw_fee)
        return MarketConfig(AssetType.BASE_CURRENCY, trading_fee, AssetType.QUOTE_CURRENCY, trading_fee,
                            withdraw_fee_amounts)
