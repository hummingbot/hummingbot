from typing import (
    Dict,
    Any
)

import numpy
from sqlalchemy import (
    BigInteger,
    Column,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship

from hummingbot.model import HummingbotBase
from hummingbot.model.decimal_type_decorator import SqliteDecimal


class Order(HummingbotBase):
    __tablename__ = "Order"
    __table_args__ = (Index("o_config_timestamp_index",
                            "config_file_path", "creation_timestamp"),
                      Index("o_market_trading_pair_timestamp_index",
                            "market", "symbol", "creation_timestamp"),
                      Index("o_market_base_asset_timestamp_index",
                            "market", "base_asset", "creation_timestamp"),
                      Index("o_market_quote_asset_timestamp_index",
                            "market", "quote_asset", "creation_timestamp"))

    id = Column(Text, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    strategy = Column(Text, nullable=False)
    market = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    base_asset = Column(Text, nullable=False)
    quote_asset = Column(Text, nullable=False)
    creation_timestamp = Column(BigInteger, nullable=False)
    order_type = Column(Text, nullable=False)
    amount = Column(SqliteDecimal(6), nullable=False)
    leverage = Column(Integer, nullable=False, default=1)
    price = Column(SqliteDecimal(6), nullable=False)
    last_status = Column(Text, nullable=False)
    last_update_timestamp = Column(BigInteger, nullable=False)
    exchange_order_id = Column(Text, nullable=True)
    position = Column(Text, nullable=True)
    status = relationship("OrderStatus", back_populates="order")
    trade_fills = relationship("TradeFill", back_populates="order")

    def __repr__(self) -> str:
        return f"Order(id={self.id}, config_file_path='{self.config_file_path}', strategy='{self.strategy}', " \
               f"market='{self.market}', symbol='{self.symbol}', base_asset='{self.base_asset}', " \
               f"quote_asset='{self.quote_asset}', creation_timestamp={self.creation_timestamp}, " \
               f"order_type='{self.order_type}', amount={self.amount}, leverage={self.leverage}, " \
               f"price={self.price}, last_status='{self.last_status}', " \
               f"last_update_timestamp={self.last_update_timestamp}), " \
               f"exchange_order_id={self.exchange_order_id}, position={self.position}"

    @staticmethod
    def to_bounty_api_json(order: "Order") -> Dict[str, Any]:
        return {
            "order_id": order.id,
            "price": numpy.format_float_positional(order.price),
            "quantity": numpy.format_float_positional(order.amount),
            "symbol": order.symbol,
            "market": order.market,
            "order_timestamp": order.creation_timestamp,
            "order_type": order.order_type,
            "base_asset": order.base_asset,
            "quote_asset": order.quote_asset,
            "raw_json": {
            }
        }
