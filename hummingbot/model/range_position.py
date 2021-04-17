#!/usr/bin/env python
import numpy
from typing import (
    Dict,
    Any
)
from sqlalchemy import (
    Column,
    Text,
    Index,
    BigInteger,
    Integer,
    Float
)
from sqlalchemy.orm import relationship

from . import HummingbotBase


class RangePosition(HummingbotBase):
    __tablename__ = "RangePosition"
    __table_args__ = (Index("rp_config_timestamp_index",
                            "config_file_path", "creation_timestamp"),
                      Index("rp_market_trading_pair_timestamp_index",
                            "market", "symbol", "creation_timestamp"),
                      )

    id = Column(Text, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    strategy = Column(Text, nullable=False)
    token_id = Column(Text, nullable=True)
    market = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    base_asset = Column(Text, nullable=False)
    quote_asset = Column(Text, nullable=False)
    fee_pct = Column(Float, nullable=False)
    lower_price = Column(Float, nullable=False)
    upper_price = Column(Float, nullable=False)
    base_amount = Column(Float, nullable=False)
    quote_amount = Column(Float, nullable=False)
    last_status = Column(Text, nullable=False)
    creation_timestamp = Column(BigInteger, nullable=False)
    last_update_timestamp = Column(BigInteger, nullable=False)
    # trade_fills = relationship("TradeFill", back_populates="order")

    def __repr__(self) -> str:
        return f"RangePosition(id={self.id}, config_file_path='{self.config_file_path}', strategy='{self.strategy}', " \
               f"token_id={self.token_id}, market='{self.market}', symbol='{self.symbol}', "\
               f"base_asset='{self.base_asset}', quote_asset='{self.quote_asset}', " \
               f"fee_pct = '{self.fee_pct}" \
               f"lower_price={self.lower_price}, upper_price='{self.upper_price}', " \
               f"base_amount='{self.base_amount}', quote_amount={self.quote_amount}, " \
               f"last_status={self.last_status}, " \
               f"creation_timestamp={self.creation_timestamp}, last_update_timestamp={self.last_update_timestamp})"
