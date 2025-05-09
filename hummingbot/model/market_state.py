#!/usr/bin/env python

from sqlalchemy import (
    Column,
    Text,
    JSON,
    Integer,
    BigInteger,
    Index
)

from . import HummingbotBase


class MarketState(HummingbotBase):
    __tablename__ = "MarketState"
    __table_args = (Index("ms_config_market_index",
                          "config_file_path", "market", unique=True),)

    id = Column(Integer, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    market = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    saved_state = Column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"MarketState(id='{self.id}', config_file_path='{self.config_file_path}', market='{self.market}', " \
            f"timestamp={self.timestamp}, saved_state={self.saved_state})"
