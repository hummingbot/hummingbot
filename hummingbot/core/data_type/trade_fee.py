import typing
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from hummingbot.connector.utils import split_hb_trading_pair, combine_to_hb_trading_pair
from hummingbot.core.event.utils import interchangeable

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


class TradeFeePercentageApplication(Enum):
    """
    Indicates how the trade fee object must be applied.

    `AddedToCost` is used for normal buy orders and third-token percentage fees for both buy and sell orders.
    `DeductedFromReturns` is used for normal sell orders and Binance-style buy orders, where an order to buy
    1000 USDT worth of BTC with a 0.1% fee will return 999 USDT worth of BTC to the user.
    """
    AddedToCost = 0
    DeductedFromReturns = 1


@dataclass
class TradeFee:
    """
    Contains the necessary information to apply the trade fee to a particular order.
    """
    percent: Optional[Decimal] = None
    percent_token: Optional[str] = None  # only set when fee charged in third token (the Binance BNB case)
    percentage_application: TradeFeePercentageApplication = TradeFeePercentageApplication.AddedToCost
    flat_fees: List[Tuple[str, Decimal]] = field(default_factory=tuple)  # list of (asset, amount) tuples

    @classmethod
    def from_json(cls, data: Dict[str, any]) -> "TradeFee":
        percent = data["percent"]
        percent_token = data.get("percent_token")
        percentage_application = data.get("percentage_application")
        percentage_application = (
            TradeFeePercentageApplication(int(percentage_application))
            if percentage_application is not None
            else TradeFeePercentageApplication.AddedToCost
        )
        flat_fees = [
            (str(fee_entry["asset"]), Decimal(fee_entry["amount"]))
            for fee_entry in data["flat_fees"]
        ]
        return TradeFee(percent, percent_token, percentage_application, tuple(flat_fees))

    def to_json(self) -> Dict[str, any]:
        return {
            "percent": float(self.percent),
            "percent_token": self.percent_token,
            "percentage_application": self.percentage_application.value,
            "flat_fees": [{"asset": asset, "amount": float(amount)}
                          for asset, amount in self.flat_fees]
        }

    def fee_amount_in_quote(
        self, trading_pair: str, price: Decimal, order_amount: Decimal, exchange: Optional["ExchangeBase"] = None
    ):
        fee_amount = Decimal("0")
        if self.percent > 0:
            fee_amount = (price * order_amount) * self.percent
        base, quote = split_hb_trading_pair(trading_pair)
        for flat_fee in self.flat_fees:
            if interchangeable(flat_fee[0], base):
                fee_amount += (flat_fee[1] * price)
            elif interchangeable(flat_fee[0], quote):
                fee_amount += flat_fee[1]
            else:
                conversion_pair = combine_to_hb_trading_pair(base=flat_fee[0], quote=quote)
                conversion_rate = self._get_exchange_rate(conversion_pair, exchange)
                fee_amount = (flat_fee[1] * conversion_rate)
        return fee_amount

    @staticmethod
    def _get_exchange_rate(trading_pair: str, exchange: Optional["ExchangeBase"] = None) -> Decimal:
        from hummingbot.core.rate_oracle.rate_oracle import RateOracle

        if exchange is not None:
            rate = exchange.get_price(trading_pair, is_buy=True)
        else:
            rate = RateOracle.get_instance().rate(trading_pair)
        return rate


@dataclass
class TradeFeeSchema:
    """
    Contains the necessary information to build a `TradeFee` object.

    NOTE: Currently, `percent_fee_token` is only specified if the percent fee is always charged in a particular
    token (e.g. the Binance BNB case). To always populate the `percent_fee_token`, this class will require
    access to the `exchange` class at runtime to determine the collateral token for the trade (e.g. for derivatives).
    This means that, if the `percent_fee_token` is specified, then the fee is always added to the trade
    costs, and `buy_percent_fee_deducted_from_returns` cannot be set to `True`.
    """
    percent_fee_token: Optional[str] = None
    maker_percent_fee_decimal: Optional[Decimal] = None
    taker_percent_fee_decimal: Optional[Decimal] = None
    buy_percent_fee_deducted_from_returns: bool = False
    maker_fixed_fees: List[Tuple[str, Decimal]] = field(default_factory=list)
    taker_fixed_fees: List[Tuple[str, Decimal]] = field(default_factory=list)

    def __post_init__(self):
        self.validate_schema()

    def validate_schema(self):
        if self.percent_fee_token is not None:
            assert not self.buy_percent_fee_deducted_from_returns
        if self.maker_percent_fee_decimal is not None:
            self.maker_percent_fee_decimal = Decimal(self.maker_percent_fee_decimal)
        if self.taker_percent_fee_decimal is not None:
            self.taker_percent_fee_decimal = Decimal(self.taker_percent_fee_decimal)
        for i in range(len(self.taker_fixed_fees)):
            self.taker_fixed_fees[i] = (self.taker_fixed_fees[i][0], Decimal(self.taker_fixed_fees[i][1]))
        for i in range(len(self.maker_fixed_fees)):
            self.maker_fixed_fees[i] = (self.maker_fixed_fees[i][0], Decimal(self.maker_fixed_fees[i][1]))
