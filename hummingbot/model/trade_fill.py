#!/usr/bin/env python
import numpy
import pandas as pd
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from sqlalchemy import (
    Column,
    ForeignKey,
    Text,
    Integer,
    Index,
    BigInteger,
    Float,
    JSON
)
from sqlalchemy.orm import (
    relationship,
    Session
)
from datetime import datetime

from . import HummingbotBase


class TradeFill(HummingbotBase):
    __tablename__ = "TradeFill"
    __table_args__ = (Index("tf_config_timestamp_index",
                            "config_file_path", "timestamp"),
                      Index("tf_market_trading_pair_timestamp_index",
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
    order_id = Column(Text, ForeignKey("Order.id"), nullable=False)
    trade_type = Column(Text, nullable=False)
    order_type = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    leverage = Column(Integer, nullable=False, default=1)
    trade_fee = Column(JSON, nullable=False)
    exchange_trade_id = Column(Text, nullable=False)
    position = Column(Text, nullable=True)
    order = relationship("Order", back_populates="trade_fills")

    def __repr__(self) -> str:
        return f"TradeFill(id={self.id}, config_file_path='{self.config_file_path}', strategy='{self.strategy}', " \
            f"market='{self.market}', symbol='{self.symbol}', base_asset='{self.base_asset}', " \
            f"quote_asset='{self.quote_asset}', timestamp={self.timestamp}, order_id='{self.order_id}', " \
            f"trade_type='{self.trade_type}', order_type='{self.order_type}', price={self.price}, amount={self.amount}, " \
            f"leverage={self.leverage}, trade_fee={self.trade_fee}, exchange_trade_id={self.exchange_trade_id}, position={self.position})"

    @staticmethod
    def get_trades(sql_session: Session,
                   strategy: str = None,
                   market: str = None,
                   trading_pair: str = None,
                   base_asset: str = None,
                   quote_asset: str = None,
                   trade_type: str = None,
                   order_type: str = None,
                   start_time: int = None,
                   end_time: int = None,
                   ) -> Optional[List["TradeFill"]]:
        filters = []
        if strategy is not None:
            filters.append(TradeFill.strategy == strategy)
        if market is not None:
            filters.append(TradeFill.market == market)
        if trading_pair is not None:
            filters.append(TradeFill.symbol == trading_pair)
        if base_asset is not None:
            filters.append(TradeFill.base_asset == base_asset)
        if quote_asset is not None:
            filters.append(TradeFill.quote_asset == quote_asset)
        if trade_type is not None:
            filters.append(TradeFill.trade_type == trade_type)
        if order_type is not None:
            filters.append(TradeFill.order_type == order_type)
        if start_time is not None:
            filters.append(TradeFill.timestamp >= start_time)
        if end_time is not None:
            filters.append(TradeFill.timestamp <= end_time)

        trades: Optional[List[TradeFill]] = (sql_session
                                             .query(TradeFill)
                                             .filter(*filters)
                                             .order_by(TradeFill.timestamp.asc())
                                             .all())
        return trades

    @classmethod
    def to_pandas(cls, trades: List):
        columns: List[str] = ["Index",
                              "Timestamp",
                              "Exchange",
                              "Market",
                              "Order_type",
                              "Side",
                              "Price",
                              "Amount",
                              "Leverage",
                              "Position",
                              "Age"]
        data = []
        index = 0
        for trade in trades:
            """
            Comment out fees
            flat_fees: List[Dict[str, Any]] = trade.trade_fee["flat_fees"]
            if len(flat_fees) == 0:
                flat_fee_str = "None"
            else:
                fee_strs = [f"{fee_dict['amount']} {fee_dict['asset']}" for fee_dict in flat_fees]
                flat_fee_str = ",".join(fee_strs)
            """

            index += 1
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            age = "n/a"
            if "//" not in trade.order_id:
                age = pd.Timestamp(int(trade.timestamp / 1e3 - int(trade.order_id[-16:]) / 1e6), unit='s').strftime('%H:%M:%S')
            data.append([
                index,
                datetime.fromtimestamp(int(trade.timestamp / 1e3)).strftime("%Y-%m-%d %H:%M:%S"),
                trade.market,
                trade.symbol,
                trade.order_type.lower(),
                trade.trade_type.lower(),
                trade.price,
                trade.amount,
                trade.leverage,
                trade.position,
                age,
            ])
        df = pd.DataFrame(data=data, columns=columns)
        df.set_index('Index', inplace=True)

        return df

    @staticmethod
    def to_bounty_api_json(trade_fill: "TradeFill") -> Dict[str, Any]:
        return {
            "market": trade_fill.market,
            "trade_id": trade_fill.exchange_trade_id,
            "price": numpy.format_float_positional(trade_fill.price),
            "quantity": numpy.format_float_positional(trade_fill.amount),
            "symbol": trade_fill.symbol,
            "trade_timestamp": trade_fill.timestamp,
            "trade_type": trade_fill.trade_type,
            "base_asset": trade_fill.base_asset,
            "quote_asset": trade_fill.quote_asset,
            "raw_json": {
                "trade_fee": trade_fill.trade_fee,
            }
        }
