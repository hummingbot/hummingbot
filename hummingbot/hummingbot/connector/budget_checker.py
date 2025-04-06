import typing
from collections import defaultdict
from copy import copy
from decimal import Decimal
from typing import Dict, List

from hummingbot.core.data_type.order_candidate import OrderCandidate

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


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
        order_candidate.populate_collateral_entries(self._exchange)
        return order_candidate

    def _get_available_balances(self, order_candidate: OrderCandidate) -> Dict[str, Decimal]:
        available_balances = {}
        balance_fn = (
            self._exchange.get_available_balance
            if not order_candidate.from_total_balances
            else self._exchange.get_balance
        )

        if order_candidate.order_collateral is not None:
            token, _ = order_candidate.order_collateral
            available_balances[token] = (
                balance_fn(token) - self._locked_collateral[token]
            )
        if order_candidate.percent_fee_collateral is not None:
            token, _ = order_candidate.percent_fee_collateral
            available_balances[token] = (
                balance_fn(token) - self._locked_collateral[token]
            )
        for entry in order_candidate.fixed_fee_collaterals:
            token, _ = entry
            available_balances[token] = (
                balance_fn(token) - self._locked_collateral[token]
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

    def _lock_available_collateral(self, order_candidate: OrderCandidate):
        for token, amount in order_candidate.collateral_dict.items():
            self._locked_collateral[token] += amount
