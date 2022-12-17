from decimal import Decimal
from typing import Iterable, Tuple


def minmax(values: Iterable[Decimal]) -> Tuple[Decimal, Decimal]:
    min_ = Decimal("Inf")
    max_ = Decimal("-Inf")
    for value in values:
        min_ = min(min_, value)
        max_ = max(max_, value)
    return min_, max_


def floor_multiple(value: int, multiple: int) -> int:
    return value - (value % multiple)


def floor_multiple_offset(value: int, multiple: int, offset: int) -> int:
    return floor_multiple(value - offset, multiple) + offset
