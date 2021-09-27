import dataclasses
from decimal import Decimal


s_decimal_zero = Decimal(0)


@dataclasses.dataclass
class TradeBand:
    time_interval: int
    required_amount: Decimal
    first_timestamp: int = None
    amount: Decimal = s_decimal_zero

    _current_ts = 0

    def tick(self, current_timestamp: float):
        self._current_ts = int(current_timestamp)
        if self.first_timestamp is not None and self._current_ts - self.first_timestamp > self.time_interval:
            self.first_timestamp = None
            self.amount = s_decimal_zero

    def check(self, amount: Decimal):
        return self.amount + amount <= self.required_amount

    def create_trade(self, amount: Decimal):
        if self.first_timestamp is None:
            self.first_timestamp = self._current_ts
        self.amount += amount
