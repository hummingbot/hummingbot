import random
from decimal import Decimal


def get_random_decimal(a: Decimal, b: Decimal, delimiter: Decimal = Decimal(10 ** 4)) -> Decimal:
    if a == b:
        return a

    a = (delimiter * a).quantize(Decimal('1') / delimiter)
    b = (delimiter * b).quantize(Decimal('1') / delimiter)
    return (random.randint(a, b) / delimiter).quantize(Decimal('1') / delimiter)


def get_percentage_of_first_from_secondary(first: Decimal, secondary: Decimal):
    return ((first * Decimal("100")) / secondary).quantize(Decimal("0.0001"))


def get_price_multiplier(start_percent: Decimal, finish_percent: Decimal, is_price_markup: bool = True) -> Decimal:
    if start_percent == finish_percent:
        return Decimal(1)
    delimiter = Decimal(10 ** 4)
    percent = get_random_decimal(start_percent, finish_percent, delimiter=delimiter)
    multiplier = (percent / Decimal(100)).quantize(Decimal('1') / delimiter)

    if is_price_markup is True:
        return Decimal(1) + multiplier
    else:
        return Decimal(1) - multiplier
