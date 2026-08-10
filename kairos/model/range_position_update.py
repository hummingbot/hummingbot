#!/usr/bin/env python
from sqlalchemy import JSON, BigInteger, Column, Float, Index, Integer, Text

from . import HummingbotBase


class RangePositionUpdate(HummingbotBase):
    """
    Table schema used when an event to update LP position(Add/Remove/Collect) is triggered.
    Stores all data needed for P&L tracking.
    """
    __tablename__ = "RangePositionUpdate"
    __table_args__ = (Index("rpu_timestamp_index", "hb_id", "timestamp"),
                      Index("rpu_config_file_index", "config_file_path", "timestamp"),
                      Index("rpu_position_index", "position_address"),
                      )

    id = Column(Integer, primary_key=True)
    hb_id = Column(Text, nullable=False)  # Order ID (e.g., "range-SOL-USDC-...")
    timestamp = Column(BigInteger, nullable=False)
    tx_hash = Column(Text, nullable=True)  # Transaction signature
    token_id = Column(Integer, nullable=False)  # Legacy field
    trade_fee = Column(JSON, nullable=False)  # Fee info JSON

    # P&L tracking fields
    config_file_path = Column(Text, nullable=True)  # Strategy config file
    market = Column(Text, nullable=True)  # Connector name (e.g., "meteora/clmm")
    order_action = Column(Text, nullable=True)  # "ADD" or "REMOVE"
    trading_pair = Column(Text, nullable=True)  # e.g., "SOL-USDC"
    position_address = Column(Text, nullable=True)  # LP position NFT address
    lower_price = Column(Float, nullable=True)  # Position lower bound
    upper_price = Column(Float, nullable=True)  # Position upper bound
    mid_price = Column(Float, nullable=True)  # Current price at time of event
    base_amount = Column(Float, nullable=True)  # Base token amount
    quote_amount = Column(Float, nullable=True)  # Quote token amount
    base_fee = Column(Float, nullable=True)  # Base fee collected (for REMOVE)
    quote_fee = Column(Float, nullable=True)  # Quote fee collected (for REMOVE)
    position_rent = Column(Float, nullable=True)  # SOL rent paid to create position (ADD only)
    position_rent_refunded = Column(Float, nullable=True)  # SOL rent refunded on close (REMOVE only)
    trade_fee_in_quote = Column(Float, nullable=True)  # Transaction fee converted to quote currency

    def __repr__(self) -> str:
        return (f"RangePositionUpdate(id={self.id}, hb_id='{self.hb_id}', "
                f"timestamp={self.timestamp}, tx_hash='{self.tx_hash}', "
                f"order_action={self.order_action}, position_address={self.position_address})")
