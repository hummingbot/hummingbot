#!/usr/bin/env python

from sqlalchemy import (
    Column,
    Text,
    Integer,
    BigInteger,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship

from . import HummingbotBase


class OrderStatus(HummingbotBase):
    __tablename__ = "OrderStatus"
    __table_args__ = (Index("os_order_id_timestamp_index",
                            "order_id", "timestamp"),
                      )

    id = Column(Integer, primary_key=True, nullable=False)
    order_id = Column(Text, ForeignKey("Order.id"), nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    status = Column(Text, nullable=False)
    order = relationship("Order", back_populates="status")
