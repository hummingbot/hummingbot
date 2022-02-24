import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.event.utils import interchangeable

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase
    from hummingbot.core.data_type.order_candidate import OrderCandidate


@dataclass
class TokenAmount:
    token: str
    amount: Decimal

    def __iter__(self):
        return iter((self.token, self.amount))


@dataclass
class TradeFeeBase(ABC):
    """
    Contains the necessary information to apply the trade fee to a particular order.
    """
    percent: Decimal = Decimal("0")
    percent_token: Optional[str] = None  # only set when fee charged in third token (the Binance BNB case)
    flat_fees: List[TokenAmount] = field(default_factory=list)  # list of (asset, amount) tuples

    def to_json(self) -> Dict[str, any]:
        return {
            "percent": float(self.percent),
            "percent_token": self.percent_token,
            "flat_fees": [{"asset": asset, "amount": float(amount)}
                          for asset, amount in self.flat_fees]
        }

    def fee_amount_in_quote(
        self, trading_pair: str, price: Decimal, order_amount: Decimal, exchange: Optional['ExchangeBase'] = None
    ) -> Decimal:
        fee_amount = Decimal("0")
        if self.percent > 0:
            fee_amount = (price * order_amount) * self.percent
        base, quote = split_hb_trading_pair(trading_pair)
        for flat_fee in self.flat_fees:
            if interchangeable(flat_fee.token, base):
                fee_amount += (flat_fee.amount * price)
            elif interchangeable(flat_fee.token, quote):
                fee_amount += flat_fee.amount
            else:
                conversion_pair = combine_to_hb_trading_pair(base=flat_fee.token, quote=quote)
                conversion_rate = self._get_exchange_rate(conversion_pair, exchange)
                fee_amount = (flat_fee.amount * conversion_rate)
        return fee_amount

    @abstractmethod
    def get_fee_impact_on_order_cost(
        self, order_candidate: 'OrderCandidate', exchange: 'ExchangeBase'
    ) -> Optional[TokenAmount]:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the cost requirements for the candidate order.
        """
        ...

    @abstractmethod
    def get_fee_impact_on_order_returns(
        self, order_candidate: 'OrderCandidate', exchange: 'ExchangeBase'
    ) -> Optional[Decimal]:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the expected returns from the candidate order.
        """
        ...

    @staticmethod
    def _get_exchange_rate(trading_pair: str, exchange: Optional["ExchangeBase"] = None) -> Decimal:
        from hummingbot.core.rate_oracle.rate_oracle import RateOracle

        if exchange is not None:
            rate = exchange.get_price(trading_pair, is_buy=True)
        else:
            rate = RateOracle.get_instance().rate(trading_pair)
        return rate


class AddedToCostTradeFee(TradeFeeBase):
    def get_fee_impact_on_order_cost(
        self, order_candidate: 'OrderCandidate', exchange: 'ExchangeBase'
    ) -> Optional[TokenAmount]:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the cost requirements for the candidate order.
        """
        ret = None
        if self.percent != Decimal("0"):
            fee_token = self.percent_token or order_candidate.order_collateral.token
            if order_candidate.order_collateral is None or fee_token != order_candidate.order_collateral.token:
                token, size = order_candidate.get_size_token_and_order_size()
                if fee_token == token:
                    exchange_rate = Decimal("1")
                else:
                    exchange_pair = combine_to_hb_trading_pair(token, fee_token)  # buy order token w/ pf token
                    exchange_rate = exchange.get_price(exchange_pair, is_buy=True)
                fee_amount = size * exchange_rate * self.percent
            else:  # self.percent_token == order_candidate.order_collateral.token
                fee_amount = order_candidate.order_collateral.amount * self.percent
            ret = TokenAmount(fee_token, fee_amount)
        return ret

    def get_fee_impact_on_order_returns(
        self, order_candidate: 'OrderCandidate', exchange: 'ExchangeBase'
    ) -> Optional[Decimal]:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the expected returns from the candidate order.
        """
        return None


class DeductedFromReturnsTradeFee(TradeFeeBase):
    def get_fee_impact_on_order_cost(
        self, order_candidate: 'OrderCandidate', exchange: 'ExchangeBase'
    ) -> Optional[TokenAmount]:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the cost requirements for the candidate order.
        """
        return None

    def get_fee_impact_on_order_returns(
        self, order_candidate: 'OrderCandidate', exchange: 'ExchangeBase'
    ) -> Optional[Decimal]:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the expected returns from the candidate order.
        """
        impact = order_candidate.potential_returns.amount * self.percent
        return impact


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
    maker_percent_fee_decimal: Decimal = Decimal("0")
    taker_percent_fee_decimal: Decimal = Decimal("0")
    buy_percent_fee_deducted_from_returns: bool = False
    maker_fixed_fees: List[TokenAmount] = field(default_factory=list)
    taker_fixed_fees: List[TokenAmount] = field(default_factory=list)

    def __post_init__(self):
        self.validate_schema()

    def validate_schema(self):
        if self.percent_fee_token is not None:
            assert not self.buy_percent_fee_deducted_from_returns
        self.maker_percent_fee_decimal = Decimal(self.maker_percent_fee_decimal)
        self.taker_percent_fee_decimal = Decimal(self.taker_percent_fee_decimal)
        for i in range(len(self.taker_fixed_fees)):
            self.taker_fixed_fees[i] = TokenAmount(
                self.taker_fixed_fees[i].token, Decimal(self.taker_fixed_fees[i].amount)
            )
        for i in range(len(self.maker_fixed_fees)):
            self.maker_fixed_fees[i] = TokenAmount(
                self.maker_fixed_fees[i].token, Decimal(self.maker_fixed_fees[i].amount)
            )
