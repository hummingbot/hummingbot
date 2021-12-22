from decimal import Decimal
from enum import Enum
from typing import NamedTuple, List, Tuple, Dict

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.event.events import interchangeable


class TradeFeeType(Enum):
    Percent = 1
    FlatFee = 2


class TradeFee(NamedTuple):
    percent: Decimal  # 0.1 = 10%
    flat_fees: List[Tuple[str, Decimal]] = []  # list of (asset, amount) ie: ("ETH", 0.05)

    def to_json(self) -> Dict[str, any]:
        return {
            "percent": float(self.percent),
            "flat_fees": [{"asset": asset, "amount": float(amount)}
                          for asset, amount in self.flat_fees]
        }

    @classmethod
    def from_json(cls, data: Dict[str, any]) -> "TradeFee":
        return TradeFee(
            Decimal(data["percent"]),
            [(fee_entry["asset"], Decimal(fee_entry["amount"]))
             for fee_entry in data["flat_fees"]]
        )

    def fee_amount_in_quote(self, trading_pair: str, price: Decimal, order_amount: Decimal):
        fee_amount = Decimal("0")
        if self.percent > 0:
            fee_amount = (price * order_amount) * self.percent
        base, quote = split_hb_trading_pair(trading_pair)
        for flat_fee in self.flat_fees:
            if interchangeable(flat_fee[0], base):
                fee_amount += (flat_fee[1] * price)
            elif interchangeable(flat_fee[0], quote):
                fee_amount += flat_fee[1]
        return fee_amount

    def order_amount_from_quote_with_fee(
        self, trading_pair: str, price: Decimal, order_size_with_fee: Decimal
    ):
        fee_amount = order_size_with_fee
        base, quote = split_hb_trading_pair(trading_pair)
        for flat_fee in self.flat_fees:
            if interchangeable(flat_fee[0], base):
                fee_amount -= (flat_fee[1] * price)
            elif interchangeable(flat_fee[0], quote):
                fee_amount -= flat_fee[1]
        order_size = order_size_with_fee / (Decimal("1") + self.percent)
        order_amount = order_size / price
        return order_amount
