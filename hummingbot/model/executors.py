from sqlalchemy import JSON, BigInteger, Boolean, Column, Float, Index, Integer, Text

from hummingbot.model import HummingbotBase


class Executors(HummingbotBase):
    __tablename__ = "Executors"
    __table_args__ = (
        Index("type", "type"),
        Index("type_timestamp", "type", "timestamp"),
        Index("timestamp", "timestamp"),
        Index("close_timestamp", "close_timestamp"),
        Index("status", "status"),
        Index("type_status", "type", "status"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    close_timestamp = Column(BigInteger, nullable=True)
    status = Column(Text, nullable=False)
    config = Column(JSON, nullable=False)
    net_pnl_pct = Column(Float, nullable=False)
    net_pnl_quote = Column(Float, nullable=False)
    cum_fees_quote = Column(Float, nullable=False)
    is_trading = Column(Boolean, nullable=False)
    custom_info = Column(JSON, nullable=False)
