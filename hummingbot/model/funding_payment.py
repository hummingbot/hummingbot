#!/usr/bin/env python
import pandas as pd
from typing import (
    List,
    Optional,
)
from sqlalchemy import (
    Column,
    Text,
    Index,
    BigInteger,
    Float,
)
from sqlalchemy.orm import (
    Session
)
from datetime import datetime

from . import HummingbotBase


class FundingPayment(HummingbotBase):
    __tablename__ = "FundingPayment"
    __table_args__ = (Index("fp_config_timestamp_index",
                            "config_file_path", "timestamp"),
                      Index("fp_market_trading_pair_timestamp_index",
                            "market", "symbol", "timestamp")
                      )

    timestamp = Column(BigInteger, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    market = Column(Text, nullable=False)
    rate = Column(Float, nullable=False)
    symbol = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"FundingPayment(timestamp={self.timestamp}, config_file_path='{self.config_file_path}', " \
               f"market='{self.market}', rate='{self.rate}' symbol='{self.symbol}', amount={self.amount}"

    @staticmethod
    def get_funding_payments(sql_session: Session,
                             timestamp: str = None,
                             market: str = None,
                             trading_pair: str = None,
                             ) -> Optional[List["FundingPayment"]]:
        filters = []
        if timestamp is not None:
            filters.append(FundingPayment.timestamp == timestamp)
        if market is not None:
            filters.append(FundingPayment.market == market)
        if trading_pair is not None:
            filters.append(FundingPayment.symbol == trading_pair)

        payments: Optional[List[FundingPayment]] = (sql_session
                                                    .query(FundingPayment)
                                                    .filter(*filters)
                                                    .order_by(FundingPayment.timestamp.asc())
                                                    .all())
        return payments

    @classmethod
    def to_pandas(cls, payments: List):
        columns: List[str] = ["Index",
                              "Timestamp",
                              "Exchange",
                              "Market",
                              "Rate",
                              "Amount"]
        data = []
        index = 0
        for payment in payments:
            index += 1
            data.append([
                index,
                datetime.fromtimestamp(int(payment.timestamp / 1e3)).strftime("%Y-%m-%d %H:%M:%S"),
                payment.market,
                payment.rate,
                payment.symbol,
                payment.amount
            ])
        df = pd.DataFrame(data=data, columns=columns)
        df.set_index('Index', inplace=True)

        return df
