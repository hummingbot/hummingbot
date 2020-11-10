from decimal import Decimal

from hummingbot.core.event.events import TradeFee


cdef class DydxFillReport:
    def __init__(self, id: str, amount: Decimal, price: Decimal, fee: Decimal):
        self.id = id
        self.amount = amount
        self.price = price
        self.fee = fee

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, DydxFillReport other):
        return self.id == other.id

    def as_dict(self):
        return {
            "id": self.id,
            "amount": str(self.amount),
            "price": str(self.price),
            "fee": str(self.fee)
        }

    @property
    def value(self) -> Decimal:
        return self.amount * self.price
