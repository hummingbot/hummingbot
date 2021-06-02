#!/usr/bin/env python
from sqlalchemy import (
    Column,
    Text,
    Index,
    BigInteger,
    Float,
    ForeignKey,
    Integer
)
from . import HummingbotBase


class RangePositionUpdate(HummingbotBase):
    __tablename__ = "RangePositionUpdate"
    __table_args__ = (Index("rpu_hb_id_timestamp_index",
                            "hb_id", "timestamp"),
                      )

    id = Column(Integer, primary_key=True, nullable=False)
    hb_id = Column(Text, ForeignKey("RangePosition.hb_id"), nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    tx_hash = Column(Text, nullable=True)
    token_id = Column(Text, nullable=False)
    base_amount = Column(Float, nullable=False)
    quote_amount = Column(Float, nullable=False)
    status = Column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"RangePositionUpdate(id={self.id}, hb_id='{self.hb_id}', " \
               f"timestamp={self.timestamp}, tx_hash={self.tx_hash}, token_id={self.token_id}" \
               f"base_amount='{self.base_amount}', quote_amount={self.quote_amount}, " \
               f"status={self.status})"
