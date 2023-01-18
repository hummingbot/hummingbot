from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Optional


class FundingInfo:
    """
    Data object that details the funding information of a perpetual market.
    """

    def __init__(self,
                 trading_pair: str,
                 index_price: Decimal,
                 mark_price: Decimal,
                 next_funding_utc_timestamp: int,
                 rate: Decimal,
                 ):
        self._trading_pair = trading_pair
        self._index_price = index_price
        self._mark_price = mark_price
        self._next_funding_utc_timestamp = next_funding_utc_timestamp
        self._rate = rate

    @property
    def trading_pair(self) -> str:
        return self._trading_pair

    @property
    def index_price(self) -> Decimal:
        return self._index_price

    @index_price.setter
    def index_price(self, index_price):
        self._index_price = index_price

    @property
    def mark_price(self) -> Decimal:
        return self._mark_price

    @mark_price.setter
    def mark_price(self, mark_price):
        self._mark_price = mark_price

    @property
    def next_funding_utc_timestamp(self) -> int:
        return self._next_funding_utc_timestamp

    @next_funding_utc_timestamp.setter
    def next_funding_utc_timestamp(self, next_funding_utc_timestamp):
        self._next_funding_utc_timestamp = next_funding_utc_timestamp

    @property
    def rate(self) -> Decimal:
        return self._rate

    @rate.setter
    def rate(self, rate):
        self._rate = rate

    def update(self, info_update: "FundingInfoUpdate"):
        update_dict = asdict(info_update)
        update_dict.pop("trading_pair")
        for key, value in update_dict.items():
            if value is not None:
                setattr(self, key, value)


@dataclass
class FundingInfoUpdate:
    trading_pair: str
    index_price: Optional[Decimal] = None
    mark_price: Optional[Decimal] = None
    next_funding_utc_timestamp: Optional[int] = None
    rate: Optional[Decimal] = None
