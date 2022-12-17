from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Literal, NamedTuple


class Candle(NamedTuple):
    # Interval start time.
    time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @staticmethod
    def meta() -> Dict[str, str]:
        return {
            "time": "unique",
        }


class Trade(NamedTuple):
    # Aggregate trade id.
    id: int = 0
    # Can have multiple trades at same time.
    time: int = 0
    price: Decimal = Decimal("0.0")
    size: Decimal = Decimal("0.0")

    @staticmethod
    def meta() -> Dict[str, str]:
        return {
            "time": "index",
        }


@dataclass(frozen=True)
class SavingsProduct:
    product_id: str
    status: Literal["PREHEATING", "PURCHASING"]
    asset: str
    can_purchase: bool
    can_redeem: bool
    purchased_amount: Decimal
    min_purchase_amount: Decimal
    limit: Decimal
    limit_per_user: Decimal

    @property
    def max_purchase_amount_for_user(self) -> Decimal:
        return min(self.limit - self.purchased_amount, self.limit_per_user)


class ConnectorException(Exception):
    """Covers errors both on the client (4XX) and server (5XX) side. Operation can be retried."""
    pass
