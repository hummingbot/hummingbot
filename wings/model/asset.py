#!/usr/bin/env python

from sqlalchemy import (
    Integer,
    Index,
    VARCHAR,
    Column
)

from . import SparrowBase


class Asset(SparrowBase):
    __tablename__ = "Asset"
    __table_args__ = (Index("symbol_name_platform_index", "symbol", "name", "platform", unique=True),)

    id = Column(Integer, primary_key=True, nullable=False)
    symbol = Column(VARCHAR(256), nullable=False)
    name = Column(VARCHAR(256), nullable=False)
    platform = Column(VARCHAR(256), default=None)

    def __repr__(self) -> str:
        return f"Asset(symbol='{self.symbol}', name='{self.name}', platform='{self.platform}')"
