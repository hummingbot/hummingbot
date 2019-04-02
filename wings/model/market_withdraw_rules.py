#!/usr/bin/env python

from sqlalchemy import Column, Numeric, Integer, Index, VARCHAR

from . import WingsBase


class MarketWithdrawRules(WingsBase):
    __tablename__ = "MarketWithdrawRules"
    __table_args__ = (Index("exchange_asset_name_index", "exchange_name", "asset_name", unique=True),)

    id = Column(Integer, primary_key=True, nullable=False)
    exchange_name = Column(VARCHAR(256), nullable=False)
    asset_name = Column(VARCHAR(256), nullable=False)
    min_withdraw_amount = Column(Numeric(precision=65, scale=18), nullable=False)
    withdraw_fee = Column(Numeric(precision=65, scale=18), nullable=False)

    def __repr__(self) -> str:
        return f"MarketWithdrawRules(exchange_name='{self.exchange_name}', asset_name='{self.asset_name}', " \
               f"min_withdraw_amount={self.min_withdraw_amount}, withdraw_fee={self.withdraw_fee})"
