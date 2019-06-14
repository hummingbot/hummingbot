#!/usr/bin/env python

from sqlalchemy import (
    Column,
    Text,
    Integer,
    Index,
    BigInteger,
    Numeric,
    Float
)

from . import HummingbotBase


class TradeFill(HummingbotBase):
    __tablename__ = "TradeFill"
    __table_args__ = (Index("tf_config_timestamp_index",
                            "config_file_path", "timestamp"),
                      Index("tf_market_symbol_timestamp_index",
                            "market", "symbol", "timestamp"),
                      Index("tf_market_base_asset_timestamp_index",
                            "market", "base_asset", "timestamp"),
                      Index("tf_market_quote_asset_timestamp_index",
                            "market", "quote_asset", "timestamp")
                      )

    id = Column(Integer, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    strategy = Column(Text, nullable=False)
    market = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    base_asset = Column(Text, nullable=False)
    quote_asset = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    order_id = Column(Text, nullable=False)
    trade_type = Column(Text, nullable=False)
    order_type = Column(Text, nullable=False)
    price = Column(Numeric(precision=65, scale=18), nullable=False)
    amount = Column(Numeric(precision=65, scale=18), nullable=False)
    trade_fee_percent = Column(Float, nullable=False)
    trade_fee_flat_fee = Column(Float, nullable=False)
    trade_fee_asset = Column(Text, nullable=False)
