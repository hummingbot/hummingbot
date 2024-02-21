#!/usr/bin/env python
from typing import List, Optional

import pandas as pd
from sqlalchemy import BigInteger, Column, Float, Index, Integer, Text
from sqlalchemy.orm import Session

from . import HummingbotBase


class PositionExecutors(HummingbotBase):
    __tablename__ = "PositionExecutors"
    __table_args__ = (Index("pe_controller_name_timestamp",
                            "controller_name", "timestamp"),
                      Index("pe_exchange_trading_pair_timestamp",
                            "exchange", "trading_pair", "timestamp"),
                      Index("pe_controller_name_exchange_trading_pair_timestamp",
                            "controller_name", "exchange", "trading_pair", "timestamp")
                      )
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, nullable=False)
    order_level = Column(Integer, nullable=True)
    exchange = Column(Text, nullable=False)
    trading_pair = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    trade_pnl = Column(Float, nullable=False)
    trade_pnl_quote = Column(Float, nullable=False)
    cum_fee_quote = Column(Float, nullable=False)
    net_pnl_quote = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)
    close_timestamp = Column(BigInteger, nullable=True)
    executor_status = Column(Text, nullable=False)
    close_type = Column(Text, nullable=True)
    entry_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    sl = Column(Float, nullable=False)
    tp = Column(Float, nullable=False)
    tl = Column(Float, nullable=False)
    open_order_type = Column(Text, nullable=False)
    take_profit_order_type = Column(Text, nullable=False)
    stop_loss_order_type = Column(Text, nullable=False)
    time_limit_order_type = Column(Text, nullable=False)
    leverage = Column(Integer, nullable=False)
    controller_name = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"PositionExecutor(timestamp={self.timestamp}, controller_name='{self.controller_name}', " \
               f"order_level={self.order_level}, " \
               f"exchange='{self.exchange}', trading_pair='{self.trading_pair}', side='{self.side}', "

    @staticmethod
    def get_position_executors(sql_session: Session,
                               controller_name: str = None,
                               exchange: str = None,
                               trading_pair: str = None,
                               ) -> Optional[List["PositionExecutors"]]:
        filters = []
        if controller_name is not None:
            filters.append(PositionExecutors.controller_name == controller_name)
        if exchange is not None:
            filters.append(PositionExecutors.exchange == exchange)
        if trading_pair is not None:
            filters.append(PositionExecutors.trading_pair == trading_pair)

        executors: Optional[List[PositionExecutors]] = (sql_session
                                                        .query(PositionExecutors)
                                                        .filter(*filters)
                                                        .order_by(PositionExecutors.timestamp.asc())
                                                        .all())
        return executors

    @classmethod
    def to_pandas(cls, executors: List):
        df = pd.DataFrame(data=[executor.to_json() for executor in executors])
        return df

    def to_json(self):
        return {
            "timestamp": self.timestamp,
            "exchange": self.exchange,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "amount": self.amount,
            "trade_pnl": self.trade_pnl,
            "trade_pnl_quote": self.trade_pnl_quote,
            "cum_fee_quote": self.cum_fee_quote,
            "net_pnl_quote": self.net_pnl_quote,
            "net_pnl": self.net_pnl,
            "close_timestamp": self.close_timestamp,
            "executor_status": self.executor_status,
            "close_type": self.close_type,
            "entry_price": self.entry_price,
            "close_price": self.close_price,
            "sl": self.sl,
            "tp": self.tp,
            "tl": self.tl,
            "open_order_type": self.open_order_type,
            "take_profit_order_type": self.take_profit_order_type,
            "stop_loss_order_type": self.stop_loss_order_type,
            "time_limit_order_type": self.time_limit_order_type,
            "leverage": self.leverage,
            "controller_name": self.controller_name,
        }
