from sqlalchemy import JSON, BigInteger, Boolean, Column, Float, Index, Text

from hummingbot.model import HummingbotBase


class Executors(HummingbotBase):
    __tablename__ = "Executors"
    __table_args__ = (
        Index("ex_type", "type"),
        Index("ex_type_timestamp", "type", "timestamp"),
        Index("ex_timestamp", "timestamp"),
        Index("ex_close_timestamp", "close_timestamp"),
        Index("ex_status", "status"),
        Index("ex_type_status", "type", "status"),
    )
    id = Column(Text, primary_key=True)
    timestamp = Column(Float, nullable=False)
    type = Column(Text, nullable=False)
    close_type = Column(Text, nullable=True)
    close_timestamp = Column(BigInteger, nullable=True)
    status = Column(Text, nullable=False)
    config = Column(JSON, nullable=False)
    net_pnl_pct = Column(Float, nullable=False)
    net_pnl_quote = Column(Float, nullable=False)
    cum_fees_quote = Column(Float, nullable=False)
    filled_amount_quote = Column(Float, nullable=False)
    is_trading = Column(Boolean, nullable=False)
    custom_info = Column(JSON, nullable=False)
