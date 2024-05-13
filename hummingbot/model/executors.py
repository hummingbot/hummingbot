from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, Column, Float, Index, Integer, Text

from hummingbot.model import HummingbotBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


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
    close_type = Column(Integer, nullable=True)
    close_timestamp = Column(BigInteger, nullable=True)
    status = Column(Integer, nullable=False)
    config = Column(JSON, nullable=False)
    net_pnl_pct = Column(Float, nullable=False)
    net_pnl_quote = Column(Float, nullable=False)
    cum_fees_quote = Column(Float, nullable=False)
    filled_amount_quote = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False)
    is_trading = Column(Boolean, nullable=False)
    custom_info = Column(JSON, nullable=False)
    controller_id = Column(Text, nullable=True)

    def to_executor_info(self) -> ExecutorInfo:
        """
        Return an ExecutorInfo object based on the current instance.
        """
        close_type = CloseType(self.close_type) if self.close_type else None
        status = RunnableStatus(self.status)
        return ExecutorInfo(
            id=self.id,
            timestamp=self.timestamp,
            type=self.type,
            close_type=close_type,
            close_timestamp=self.close_timestamp,
            status=status,
            config=self.config,
            net_pnl_pct=Decimal(self.net_pnl_pct),
            net_pnl_quote=Decimal(self.net_pnl_quote),
            cum_fees_quote=Decimal(self.cum_fees_quote),
            filled_amount_quote=Decimal(self.filled_amount_quote),
            is_active=self.is_active,
            is_trading=self.is_trading,
            custom_info=self.custom_info,
            controller_id=self.controller_id,
        )
