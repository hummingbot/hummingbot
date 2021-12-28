import typing
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.trade_fee import TradeFee, TradeFeePercentageApplication
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.utils.estimate_fee import build_trade_fee

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


@dataclass
class TokenAmount:
    token: str
    amount: Decimal

    def __iter__(self):
        return iter((self.token, self.amount))


@dataclass
class OrderCandidate:
    """
    This class contains a full picture of the impact of a potential order on the user account.

    It can return a dictionary with the base collateral required for an order, the percentage-fee collateral
    and the fixed-fee collaterals, and any combination of those. In addition, it contains a field sizing
    the potential return of an order.

    It also provides logic to adjust the order size, the collateral values, and the return based on
    a dictionary of currently available assets in the user account.
    """
    trading_pair: str
    is_maker: bool
    order_type: OrderType
    order_side: TradeType
    amount: Decimal
    price: Decimal
    order_collateral: Optional[TokenAmount] = field(default=None, init=False)
    percent_fee_collateral: Optional[TokenAmount] = field(default=None, init=False)
    fixed_fee_collaterals: List[TokenAmount] = field(default=list, init=False)
    potential_returns: Optional[TokenAmount] = field(default=None, init=False)
    resized: bool = field(default=False, init=False)

    @property
    def collateral_dict(self) -> Dict:
        cd = defaultdict(lambda: Decimal("0"))
        if self.order_collateral is not None:
            cd[self.order_collateral.token] += self.order_collateral.amount
        if self.percent_fee_collateral is not None:
            cd[self.percent_fee_collateral.token] += self.percent_fee_collateral.amount
        for entry in self.fixed_fee_collaterals:
            cd[entry.token] += entry.amount
        return cd

    @property
    def is_zero_order(self) -> bool:
        return self.amount == Decimal("0")

    def adjust_from_balances(self, available_balances: Dict[str, Decimal]):
        if not self.is_zero_order:
            self._adjust_for_order_collateral(available_balances)
        if not self.is_zero_order:
            self._adjust_for_percent_fee_collateral(available_balances)
        if not self.is_zero_order:
            self._adjust_for_fixed_fee_collaterals(available_balances)

    def set_to_zero(self):
        self.scale_order(scaler=Decimal("0"))

    def scale_order(self, scaler: Decimal):
        self.amount *= scaler
        if self.order_collateral is not None:
            self.order_collateral.amount *= scaler
        if self.percent_fee_collateral is not None:
            self.percent_fee_collateral.amount *= scaler
        if self.potential_returns is not None:
            self.potential_returns.amount *= scaler
        if self.is_zero_order:
            self.order_collateral = None
            self.percent_fee_collateral = None
            self.fixed_fee_collaterals = []
            self.potential_returns = None
        self.resized = True

    def _adjust_for_order_collateral(self, available_balances: Dict[str, Decimal]):
        if self.order_collateral is not None:
            token, amount = self.order_collateral
            if available_balances[token] < amount:
                scaler = available_balances[token] / amount
                self.scale_order(scaler)

    def _adjust_for_percent_fee_collateral(self, available_balances: Dict[str, Decimal]):
        if self.percent_fee_collateral is not None:
            token, amount = self.percent_fee_collateral
            if token == self.order_collateral.token:
                amount += self.order_collateral.amount
            if available_balances[token] < amount:
                scaler = available_balances[token] / amount
                self.scale_order(scaler)

    def _adjust_for_fixed_fee_collaterals(self, available_balances: Dict[str, Decimal]):
        oc_token = self.order_collateral.token if self.order_collateral is not None else None
        pfc_token = self.percent_fee_collateral.token if self.percent_fee_collateral is not None else None
        oc_amount, pfc_amount = self._get_order_and_pf_collateral_amounts_for_ff_adjustment()

        for collateral_entry in self.fixed_fee_collaterals:
            ffc_token, ffc_amount = collateral_entry
            available_balance = available_balances[ffc_token]
            if available_balance < ffc_amount:
                self.scale_order(scaler=Decimal("0"))
                break
            if oc_token is not None and ffc_token == oc_token and available_balance < ffc_amount + oc_amount:
                scaler = (available_balance - ffc_amount) / oc_amount
                self.scale_order(scaler)
                oc_amount, pfc_amount = self._get_order_and_pf_collateral_amounts_for_ff_adjustment()
            if pfc_token is not None and ffc_token == pfc_token and available_balance < ffc_amount + pfc_amount:
                scaler = (available_balance - ffc_amount) / pfc_amount
                self.scale_order(scaler)
                oc_amount, pfc_amount = self._get_order_and_pf_collateral_amounts_for_ff_adjustment()
            if self.is_zero_order:
                break

    def _get_order_and_pf_collateral_amounts_for_ff_adjustment(self) -> Tuple[Decimal, Decimal]:
        if self.order_collateral is not None:
            oc_token, oc_amount = self.order_collateral
        else:
            oc_token = None
            oc_amount = Decimal("0")
        if self.percent_fee_collateral is not None:
            pfc_token, pfc_amount = self.percent_fee_collateral
            if oc_token is not None and pfc_token == oc_token:
                oc_amount += pfc_amount
                pfc_amount = Decimal("0")
        else:
            pfc_amount = Decimal("0")
        return oc_amount, pfc_amount


class BudgetChecker:
    def __init__(self, exchange: "ExchangeBase"):
        """
        Provides utilities for strategies to check the potential impact of order proposals on the user account balances.

        Mainly used to determine if sufficient balance is available to place a set of strategy-proposed orders.
        The strategy can size a list of proposed order candidates by calling the `adjust_candidates` method.

        For a more fine-grained control, the strategy can call `adjust_candidate_and_lock_available_collateral`
        for each one of the orders it intends to place. On each call, the `BudgetChecker` locks in the collateral
        amount needed for that order and makes it unavailable for the following hypothetical orders.
        Once the orders are sent to the exchange, the strategy must call `reset_locked_collateral` to
        free the hypothetically locked assets for the next set of checks.

        :param exchange: The exchange against which available collateral assets will be checked.
        """
        self._exchange = exchange
        self._locked_collateral: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    def reset_locked_collateral(self):
        """
        Frees collateral assets locked for hypothetical orders.
        """
        self._locked_collateral.clear()

    def adjust_candidates(
        self, order_candidates: List[OrderCandidate], all_or_none: bool = True
    ) -> List[OrderCandidate]:
        """
        Fills in the collateral and returns fields of the order candidates.
        If there is insufficient assets to cover the collateral requirements, the order amount is adjusted.

        See the doc string for `adjust_candidate` to learn more about how the adjusted order
        amount is derived.

        :param order_candidates: A list of candidate orders to check and adjust.
        :param all_or_none: Should the order amount be set to zero on insufficient balance.
        :return: The list of adjusted order candidates.
        """
        self.reset_locked_collateral()
        adjusted_candidates = [
            self.adjust_candidate_and_lock_available_collateral(order_candidate, all_or_none)
            for order_candidate in order_candidates
        ]
        self.reset_locked_collateral()
        return adjusted_candidates

    def adjust_candidate_and_lock_available_collateral(
        self, order_candidate: OrderCandidate, all_or_none: bool = True
    ) -> OrderCandidate:
        """
        Fills in the collateral and returns fields of the order candidates.
        If there is insufficient assets to cover the collateral requirements, the order amount is adjusted.

        See the doc string for `adjust_candidate` to learn more about how the adjusted order
        amount is derived.

        This method also locks in the collateral amount for the given collateral token and makes
        it unavailable on subsequent calls to this method until the `reset_locked_collateral`
        method is called.

        :param order_candidate: The candidate order to check and adjust.
        :param all_or_none: Should the order amount be set to zero on insufficient balance.
        :return: The adjusted order candidate.
        """
        adjusted_candidate = self.adjust_candidate(order_candidate, all_or_none)
        self._lock_available_collateral(adjusted_candidate)
        return adjusted_candidate

    def adjust_candidate(
        self, order_candidate: OrderCandidate, all_or_none: bool = True
    ) -> OrderCandidate:
        """
        Fills in the collateral and returns fields of the order candidates.

        If there is insufficient collateral to cover the proposed order amount and
        the `all_or_none` parameter is set to `False`, the order amount will be adjusted
        to the greatest amount that the remaining collateral can provide for. If the parameter
        is set to `True`, the order amount is set to zero.

        :param order_candidate: The candidate order to be checked and adjusted.
        :param all_or_none: Should the order amount be set to zero on insufficient balance.
        :return: The adjusted order candidate.
        """
        order_candidate = self.populate_collateral_entries(order_candidate)
        available_balances = self._get_available_balances(order_candidate)
        order_candidate.adjust_from_balances(available_balances)
        if order_candidate.resized:
            if all_or_none:
                order_candidate.set_to_zero()
            else:
                order_candidate = self._quantize_adjusted_order(order_candidate)
        return order_candidate

    def populate_collateral_entries(self, order_candidate: OrderCandidate) -> OrderCandidate:
        """
        Populates the collateral and returns fields of the order candidates.

        This implementation assumes a spot-specific configuration for collaterals (i.e. the quote
        token for buy orders, and base token for sell orders). It can be overridden to provide other
        configurations.

        :param order_candidate: The candidate order to check and adjust.
        :return: The adjusted order candidate.
        """
        order_candidate = copy(order_candidate)

        order_candidate = self._populate_order_collateral_entry(order_candidate)
        fee = self._get_fee(order_candidate)
        order_candidate = self._populate_percent_fee_collateral_entry(order_candidate, fee)
        order_candidate = self._populate_fixed_fee_collateral_entries(order_candidate, fee)
        order_candidate = self._populate_potential_returns_entry(order_candidate, fee)

        return order_candidate

    def _populate_order_collateral_entry(self, order_candidate: OrderCandidate) -> OrderCandidate:
        oc_token = self._get_order_collateral_token(order_candidate)
        if oc_token is not None:
            oc_amount = self._get_order_collateral_amount(order_candidate, oc_token)
            order_candidate.order_collateral = TokenAmount(oc_token, oc_amount)
        return order_candidate

    def _get_order_collateral_token(self, order_candidate: OrderCandidate) -> Optional[str]:
        trading_pair = order_candidate.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if order_candidate.order_side == TradeType.BUY:
            oc_token = quote
        else:
            oc_token = base
        return oc_token

    def _get_order_collateral_amount(
        self, order_candidate: OrderCandidate, order_collateral_token: str
    ) -> Decimal:
        order_size, size_token = self._get_order_size_and_size_token(order_candidate)
        size_collateral_price = self._get_size_collateral_price(order_candidate, order_collateral_token)
        oc_amount = order_size * size_collateral_price
        return oc_amount

    def _populate_percent_fee_collateral_entry(self, order_candidate: OrderCandidate, fee: TradeFee) -> OrderCandidate:
        if fee.percent is not None and fee.percent_token is None:
            fee.percent_token = order_candidate.order_collateral.token
        if fee.percent is not None and fee.percentage_application == TradeFeePercentageApplication.AddedToCost:
            if order_candidate.order_collateral is None or fee.percent_token != order_candidate.order_collateral.token:
                size, token = self._get_order_size_and_size_token(order_candidate)
                if fee.percent_token == token:
                    exchange_rate = Decimal("1")
                else:
                    exchange_pair = combine_to_hb_trading_pair(token, fee.percent_token)  # buy order token w/ pf token
                    exchange_rate = self._exchange.get_price(exchange_pair, is_buy=True)
                amount = size * exchange_rate * fee.percent
            else:  # fee.percent_token == order_candidate.order_collateral.token
                amount = order_candidate.order_collateral.amount * fee.percent
            order_candidate.percent_fee_collateral = TokenAmount(fee.percent_token, amount)

        return order_candidate

    @staticmethod
    def _populate_fixed_fee_collateral_entries(order_candidate: OrderCandidate, fee: TradeFee) -> OrderCandidate:
        order_candidate.fixed_fee_collaterals = []
        for token, amount in fee.flat_fees:
            order_candidate.fixed_fee_collaterals.append(TokenAmount(token, amount))
        return order_candidate

    def _populate_potential_returns_entry(self, order_candidate: OrderCandidate, fee: TradeFee) -> OrderCandidate:
        r_token = self._get_returns_token(order_candidate)
        if r_token is not None:
            r_amount = self._get_returns_amount(order_candidate)
            if fee.percentage_application == TradeFeePercentageApplication.DeductedFromReturns:
                r_amount *= Decimal("1") - fee.percent
            order_candidate.potential_returns = TokenAmount(r_token, r_amount)
        return order_candidate

    def _get_returns_token(self, order_candidate: OrderCandidate) -> Optional[str]:
        trading_pair = order_candidate.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if order_candidate.order_side == TradeType.BUY:
            r_token = base
        else:
            r_token = quote
        return r_token

    def _get_returns_amount(self, order_candidate: OrderCandidate) -> Decimal:
        if order_candidate.order_side == TradeType.BUY:
            r_amount = order_candidate.amount
        else:
            r_amount = order_candidate.amount * order_candidate.price
        return r_amount

    def _get_available_balances(self, order_candidate: OrderCandidate) -> Dict[str, Decimal]:
        available_balances = {}

        if order_candidate.order_collateral is not None:
            token, _ = order_candidate.order_collateral
            available_balances[token] = (
                self._exchange.get_available_balance(token) - self._locked_collateral[token]
            )
        if order_candidate.percent_fee_collateral is not None:
            token, _ = order_candidate.percent_fee_collateral
            available_balances[token] = (
                self._exchange.get_available_balance(token) - self._locked_collateral[token]
            )
        for entry in order_candidate.fixed_fee_collaterals:
            token, _ = entry
            available_balances[token] = (
                self._exchange.get_available_balance(token) - self._locked_collateral[token]
            )

        return available_balances

    def _quantize_adjusted_order(self, order_candidate: OrderCandidate) -> OrderCandidate:
        trading_pair = order_candidate.trading_pair
        adjusted_amount = order_candidate.amount
        quantized_amount = self._exchange.quantize_order_amount(trading_pair, adjusted_amount)

        if adjusted_amount != quantized_amount:
            order_candidate.amount = quantized_amount
            order_candidate = self.populate_collateral_entries(order_candidate)

        return order_candidate

    def _get_size_collateral_price(
        self, order_candidate: OrderCandidate, order_collateral_token: str
    ) -> Decimal:
        _, size_token = self._get_order_size_and_size_token(order_candidate)
        base, quote = split_hb_trading_pair(order_candidate.trading_pair)

        if order_collateral_token == size_token:
            price = Decimal("1")
        elif order_collateral_token == base:  # size_token == quote
            price = Decimal("1") / order_candidate.price
        elif order_collateral_token == quote:  # size_token == base
            price = order_candidate.price
        else:
            size_collateral_pair = combine_to_hb_trading_pair(size_token, order_collateral_token)
            price = self._exchange.get_price(size_collateral_pair, is_buy=True)  # we are buying

        return price

    @staticmethod
    def _get_order_size_and_size_token(order_candidate: OrderCandidate) -> typing.Tuple[Decimal, str]:
        trading_pair = order_candidate.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if order_candidate.order_side == TradeType.BUY:
            order_size = order_candidate.amount * order_candidate.price
            size_token = quote
        else:
            order_size = order_candidate.amount
            size_token = base
        return order_size, size_token

    def _get_fee(self, order_candidate: OrderCandidate) -> TradeFee:
        trading_pair = order_candidate.trading_pair
        price = order_candidate.price
        base, quote = split_hb_trading_pair(trading_pair)
        fee = build_trade_fee(
            self._exchange.name,
            order_candidate.is_maker,
            base,
            quote,
            order_candidate.order_type,
            order_candidate.order_side,
            order_candidate.amount,
            price,
        )

        return fee

    def _lock_available_collateral(self, order_candidate: OrderCandidate):
        for token, amount in order_candidate.collateral_dict.items():
            self._locked_collateral[token] += amount
