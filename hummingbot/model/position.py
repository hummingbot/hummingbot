from sqlalchemy import JSON, BigInteger, Column, Index, Text

from . import HummingbotBase
from .decimal_type_decorator import SqliteDecimal


class Position(HummingbotBase):
    """
    Database model for storing positions held by executors.
    """
    __tablename__ = "Position"
    __table_args__ = (Index("p_controller_id_timestamp_index",
                            "controller_id", "timestamp"),
                      Index("p_connector_name_trading_pair_timestamp_index",
                            "connector_name", "trading_pair", "timestamp"))

    id = Column(Text, primary_key=True, nullable=False)
    controller_id = Column(Text, nullable=False)
    connector_name = Column(Text, nullable=False)
    trading_pair = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    volume_traded_quote = Column(SqliteDecimal(6), nullable=False)
    amount = Column(SqliteDecimal(6), nullable=False)
    breakeven_price = Column(SqliteDecimal(6), nullable=False)
    unrealized_pnl_quote = Column(SqliteDecimal(6), nullable=False)
    cum_fees_quote = Column(SqliteDecimal(6), nullable=False)
    filled_orders = Column(JSON, nullable=False)

    def __repr__(self) -> str:
        return (f"Position(id='{self.id}', config_file_path='{self.config_file_path}', "
                f"strategy='{self.strategy}', market='{self.market}', "
                f"trading_pair='{self.trading_pair}', timestamp={self.timestamp}, "
                f"volume_traded_quote={self.volume_traded_quote}, amount={self.amount}, "
                f"breakeven_price={self.breakeven_price}, unrealized_pnl_quote={self.unrealized_pnl_quote}, "
                f"cum_fees_quote={self.cum_fees_quote})")
