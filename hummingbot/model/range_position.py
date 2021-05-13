#!/usr/bin/env python
from sqlalchemy import (
    Column,
    Text,
    Index,
    BigInteger,
    Float
)
from . import HummingbotBase


class RangePosition(HummingbotBase):
    __tablename__ = "RangePosition"
    __table_args__ = (Index("rp_config_timestamp_index",
                            "config_file_path", "creation_timestamp"),
                      Index("rp_connector_trading_pair_timestamp_index",
                            "connector", "trading_pair", "creation_timestamp")
                      )
    hb_id = Column(Text, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    strategy = Column(Text, nullable=False)
    tx_hash = Column(Text, nullable=True)
    connector = Column(Text, nullable=False)
    trading_pair = Column(Text, nullable=False)
    fee_tier = Column(Text, nullable=False)
    lower_price = Column(Float, nullable=False)
    upper_price = Column(Float, nullable=False)
    base_amount = Column(Float, nullable=False)
    quote_amount = Column(Float, nullable=False)
    status = Column(Text, nullable=False)
    creation_timestamp = Column(BigInteger, nullable=False)
    last_update_timestamp = Column(BigInteger, nullable=False)

    def __repr__(self) -> str:
        return f"RangePosition(hb_id={self.hb_id}, config_file_path='{self.config_file_path}', strategy='{self.strategy}', " \
               f"tx_hash={self.tx_hash}, connector='{self.connector}', trading_pair='{self.trading_pair}', "\
               f"fee_tier = '{self.fee_tier}" \
               f"lower_price={self.lower_price}, upper_price='{self.upper_price}', " \
               f"base_amount='{self.base_amount}', quote_amount={self.quote_amount}, " \
               f"status={self.status}, " \
               f"creation_timestamp={self.creation_timestamp}, last_update_timestamp={self.last_update_timestamp})"
