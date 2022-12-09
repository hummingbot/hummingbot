#!/usr/bin/env python
from sqlalchemy import JSON, BigInteger, Column, Index, Integer, Text

from . import HummingbotBase


class RangePositionUpdate(HummingbotBase):
    """
    Table schema used when an event to update LP position(Add/Remove/Collect) is triggered.
    """
    __tablename__ = "RangePositionUpdate"
    __table_args__ = (Index("rpu_timestamp_index",
                            "hb_id", "timestamp"),
                      )

    id = Column(Integer, primary_key=True)
    hb_id = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    tx_hash = Column(Text, nullable=True)
    token_id = Column(Integer, nullable=False)
    trade_fee = Column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"RangePositionUpdate(id={self.id}, hb_id='{self.hb_id}', " \
               f"timestamp={self.timestamp}, tx_hash='{self.tx_hash}', token_id={self.token_id}" \
               f"trade_fee={self.trade_fee})"
