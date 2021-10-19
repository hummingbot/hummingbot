import dataclasses
from random import randint
from decimal import Decimal
from typing import Tuple, List

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.stones.utils import get_random_decimal, get_percentage_of_first_from_secondary

s_decimal_zero = Decimal(0)
hundred = Decimal('100')


@dataclasses.dataclass
class OrderLevel:
    number: str
    market: ExchangeBase
    trading_pair: str
    min_percentage_price_change: Decimal
    max_percentage_price_change: Decimal
    min_order_amount: Decimal
    max_order_amount: Decimal
    percentage_of_liquidity: Decimal
    is_buy: bool

    _id = randint(0, 100000000)

    def __hash__(self):
        return f"{self.__str__()}_{self._id}".__hash__()

    def __str__(self):
        return f"{self.market.name}_{self.trading_pair}_{'buy' if self.is_buy is True else 'sell'}_{self.number}_level"

    def __repr__(self):
        return self.__str__()

    def calculate_price(self, price: Decimal, is_buy: bool):
        price_delta = price * get_random_decimal(self.min_percentage_price_change, self.max_percentage_price_change) / hundred
        return price - price_delta if is_buy is True else price + price_delta

    def get_trades_data(self, is_buy: bool, price: Decimal, liquidity: Decimal) -> List[Tuple]:
        results = []
        if liquidity < self.min_order_amount:
            pass
        elif self.min_order_amount <= liquidity <= self.max_order_amount:
            results.append((is_buy, self.calculate_price(price, is_buy), liquidity, self))
        elif liquidity > self.max_order_amount:
            order_amount: Decimal = get_random_decimal(self.min_order_amount, self.max_order_amount)
            results.append((is_buy, self.calculate_price(price, is_buy), order_amount, self))
            results += self.get_trades_data(is_buy=is_buy, price=price, liquidity=liquidity - order_amount)

        return results

    def is_at_level_of(self, oracle_price: Decimal, order_price: Decimal, amount: Decimal, is_buy: bool, **kwargs):
        current_percent = get_percentage_of_first_from_secondary(first=order_price, secondary=oracle_price)
        current_different = (current_percent - Decimal('100'))

        if is_buy is True:
            is_price_at_level_of = self.min_percentage_price_change <= Decimal('-1') * current_different <= self.max_percentage_price_change
        else:
            is_price_at_level_of = self.min_percentage_price_change <= current_different <= self.max_percentage_price_change

        is_amount_at_level_of = self.min_order_amount <= amount <= self.max_order_amount
        return is_price_at_level_of and is_amount_at_level_of
