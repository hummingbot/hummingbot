#!/usr/bin/env python

from sqlalchemy import (
    ForeignKey,
    Integer,
    Index,
    Column,
    DateTime,
    Numeric,
    VARCHAR
)
from sqlalchemy.orm import relationship

from . import SparrowBase


class MarketData(SparrowBase):
    __tablename__ = "MarketData"
    __table_args__ = (Index("asset_data_source_timestamp_index", "asset_id", "data_source", "timestamp", unique=True),
                      Index("timestamp_data_source_index", "timestamp", "data_source"),
                      Index("timestamp_asset_market_cap_index", "timestamp", "asset_id", "market_cap"),
                      Index("timestamp_asset_volume_index", "timestamp", "asset_id", "volume"))

    id = Column(Integer, primary_key=True, nullable=False)
    asset_id = Column(ForeignKey("Asset.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    data_source = Column(VARCHAR(256), nullable=False)
    price = Column(Numeric(precision=48, scale=18))
    market_cap = Column(Numeric(precision=48, scale=18))
    supply = Column(Numeric(precision=48, scale=18))
    volume = Column(Numeric(precision=48, scale=18))
    asset = relationship("Asset", lazy="joined")

    def __repr__(self) -> str:
        return f"MarketData(symbol='{self.asset.symbol}', name='{self.asset.name}', " \
               f"platform='{self.asset.platform}', timestamp={self.timestamp}, data_source='{self.data_source}', " \
               f"price={self.price}, market_cap={self.market_cap}, supply={self.supply}, volume={self.volume})"
