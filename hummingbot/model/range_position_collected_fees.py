#!/usr/bin/env python
from sqlalchemy import Column, Float, Index, Integer, Text

from . import HummingbotBase


class RangePositionCollectedFees(HummingbotBase):
    """
    Table schema used when LP feesmare claimed.
    """
    __tablename__ = "RangePositionCollectedFees"
    __table_args__ = (Index("rpf_id_index",
                            "token_id", "config_file_path"),
                      )
    id = Column(Integer, primary_key=True, nullable=False)
    config_file_path = Column(Text, nullable=False)
    strategy = Column(Text, nullable=False)
    token_id = Column(Integer, nullable=False)
    token_0 = Column(Text, nullable=False)
    token_1 = Column(Text, nullable=False)
    claimed_fee_0 = Column(Float, nullable=False)
    claimed_fee_1 = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"RangePositionCollectedFees(id={self.id}, config_file_path='{self.config_file_path}', strategy='{self.strategy}', " \
               f"token_id={self.token_id}, token_0='{self.token_0}', token_1='{self.token_1}', " \
               f"claimed_fee_0={self.claimed_fee_0}, claimed_fee_1={self.claimed_fee_1})"
