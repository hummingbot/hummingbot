from typing import NamedTuple
from decimal import Decimal


class CeloExchangeRate(NamedTuple):
    from_token: str
    from_amount: Decimal
    to_token: str
    to_amount: Decimal
