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

    def __repr__(self) -> str:
        return f"OrderStatus(id={self.id}, order_id='{self.order_id}', timestamp={self.timestamp}, " \
            f"status='{self.status}')"
