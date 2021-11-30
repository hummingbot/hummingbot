import typing
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.event.events import OrderType, TradeFee, TradeType

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


@dataclass
class OrderCandidate:
    trading_pair: str
    order_type: OrderType
    order_side: TradeType
    amount: Decimal
    price: Decimal
    collateral_amount: Optional[Decimal] = None
    collateral_token: Optional[str] = None


class BudgetChecker:
    def __init__(self, exchange: "ExchangeBase"):
        """
        Provides utilities for strategies to check if the required assets for trades are available.

        Used to determine if sufficient balance is available to place a set of strategy-proposed orders.
        The strategy can size a list of proposed order candidates by calling the `adjust_candidates` method.

        For a more fine-grained control, the strategy can call `adjust_candidate_and_lock_available_collateral`
        for each one of the orders it intends to place. On each call, the `BudgetChecker` locks in the collateral
        amount needed for that order and makes it unavailable for the following hypothetical orders.
        Once the orders are sent to the exchange, the strategy must call `reset_locked_collateral` to
        free the hypothetically locked assets for the next set of checks.

        The default implementation covers the general case, with the exception of `_get_collateral_token`
        and `_get_fee` (and perhaps `_get_collateral_adjustment_for_fees`) methods which are spot-specific
        and may need to be overridden for the specific exchange configuration.

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
        Fills in the collateral token and collateral amount fields for the order candidates.
        If there is insufficient assets to cover the collateral, the order amount is adjusted.

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
        Fills in the collateral token and collateral amount fields for the order candidate.
        If there is insufficient assets to cover the collateral, the order amount is adjusted.

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
        Fills in the collateral token and collateral amount fields for the order candidate.

        If there is insufficient collateral to cover the proposed order amount and
        the `all_or_none` parameter is set to `False`, the order amount will be adjusted
        to the greatest amount that the remaining collateral can provide for. If the parameter
        is set to `True`, the order amount is set to zero.

        :param order_candidate: The candidate order to check and adjust.
        :param all_or_none: Should the order amount be set to zero on insufficient balance.
        :return: The adjusted order candidate.
        """
        adjusted_candidate = self.populate_collateral_fields(order_candidate)
        available_collateral = self._exchange.get_available_balance(adjusted_candidate.collateral_token)
        locked_collateral = self._locked_collateral[adjusted_candidate.collateral_token]
        available_collateral -= locked_collateral
        required_collateral_amount = adjusted_candidate.collateral_amount

        if available_collateral < required_collateral_amount:
            if all_or_none:
                adjusted_candidate.amount = Decimal("0")
                adjusted_candidate.collateral_amount = Decimal("0")
            else:
                adjusted_candidate = self._reduce_order_and_collateral_amounts(adjusted_candidate, available_collateral)

        return adjusted_candidate

    def populate_collateral_fields(self, order_candidate: OrderCandidate) -> OrderCandidate:
        """
        Populates the required collateral amount and the collateral token fields for the given order.

        This implementation assumes a spot-specific configuration for collaterals (i.e. the quote
        token for buy orders, and base token for sell). It can be overridden to provide other
        configurations.

        :param order_candidate: The candidate order to check and adjust.
        :return: The adjusted order candidate.
        """
        populated_candidate = copy(order_candidate)

        populated_candidate.collateral_token = self._get_collateral_token(populated_candidate)
        required_collateral = self._get_base_required_collateral(populated_candidate)
        adjustment = self._get_collateral_adjustment_for_fees(populated_candidate)
        required_collateral += adjustment

        populated_candidate.collateral_amount = required_collateral

        return populated_candidate

    def _get_collateral_token(self, order_candidate: OrderCandidate) -> str:
        trading_pair = order_candidate.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if order_candidate.order_side == TradeType.BUY:
            collateral_token = quote
        else:
            collateral_token = base
        return collateral_token

    def _get_base_required_collateral(self, order_candidate: OrderCandidate) -> Decimal:
        order_size, size_token = self._get_order_size_and_size_token(order_candidate)
        size_collateral_price = self._get_size_collateral_price(order_candidate)
        required_collateral = order_size * size_collateral_price
        return required_collateral

    def _reduce_order_and_collateral_amounts(
        self, order_candidate: OrderCandidate, available_collateral: Decimal
    ) -> OrderCandidate:
        adjusted_amount = self._get_adjusted_amount(order_candidate, available_collateral)
        adjusted_amount = self._quantize_adjusted_amount(order_candidate, adjusted_amount)

        adjusted_candidate = copy(order_candidate)
        adjusted_candidate.amount = adjusted_amount
        adjusted_candidate.collateral_amount = available_collateral

        return adjusted_candidate

    def _get_adjusted_amount(self, order_candidate: OrderCandidate, target_collateral: Decimal) -> Decimal:
        order_size, size_token = self._get_order_size_and_size_token(order_candidate)
        size_collateral_price = self._get_size_collateral_price(order_candidate)
        target_size = target_collateral / size_collateral_price

        base, _ = split_hb_trading_pair(order_candidate.trading_pair)
        if size_token == base:
            adjusted_quote_size = target_size * order_candidate.price
        else:
            adjusted_quote_size = target_size

        fee = self._get_fee(order_candidate)
        adjusted_amount = fee.order_amount_from_quote_with_fee(
            order_candidate.trading_pair, order_candidate.price, adjusted_quote_size
        )

        return adjusted_amount

    def _quantize_adjusted_amount(self, order_candidate: OrderCandidate, adjusted_amount: Decimal) -> Decimal:
        _, size_token = self._get_order_size_and_size_token(order_candidate)
        trading_pair = order_candidate.trading_pair
        base, quote = split_hb_trading_pair(order_candidate.trading_pair)

        if size_token == base:
            adjusted_amount = self._exchange.quantize_order_amount(trading_pair, adjusted_amount)
        else:  # size_token == quote
            adjusted_amount = self._exchange.quantize_order_price(trading_pair, adjusted_amount)

        return adjusted_amount

    def _get_size_collateral_price(self, order_candidate: OrderCandidate) -> Decimal:
        _, size_token = self._get_order_size_and_size_token(order_candidate)
        collateral_token = order_candidate.collateral_token
        base, quote = split_hb_trading_pair(order_candidate.trading_pair)

        if collateral_token == size_token:
            price = Decimal("1")
        elif collateral_token == base:  # size_token == quote
            price = Decimal("1") / order_candidate.price
        elif collateral_token == quote:  # size_token == base
            price = order_candidate.price
        else:
            # # todo: verify soundness (i.e. this price target will move)
            # size_collateral_pair = f"{size_token}-{collateral_token}"
            # price = self._exchange.get_price(size_collateral_pair, is_buy=True)
            raise NotImplementedError(
                f"Third-token collaterals not yet supported."
                f" Base token = {base}, quote token = {quote}, collateral token = {collateral_token}."
            )

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

    def _get_collateral_adjustment_for_fees(self, order_candidate: OrderCandidate) -> Decimal:
        trading_pair = order_candidate.trading_pair
        amount = order_candidate.amount
        price = order_candidate.price
        fee = self._get_fee(order_candidate)

        fee_adjustment = fee.fee_amount_in_quote(trading_pair, price, amount)

        return fee_adjustment

    def _get_fee(self, order_candidate: OrderCandidate) -> TradeFee:
        """
        The default implementation assumes that, for buy orders, the trading fee is
        charged on top of the order quoted amount; and it assumes that, for sell orders,
        the fee is deducted from the returns after the sell has completed.

        Example:
             - Buy Order
                 The user is submitting an order to buy 100 USDT worth of BTC on an exchange
                 with a 1% fee. The required collateral will be 101 USDT (i.e. the adjustment term is 1).
             - Sell Order
                 The user is submitting an order to sell 1 ETH. The required collateral
                 is 1 ETH, because the exchange will deduct the 1% fee from the quote asset
                 returns after the sale has taken place (i.e. the adjustment term is zero).

        Some exchanges can deduct the transaction fee from the buy order amount
        (i.e. in the buy order example above, the user will only obtain 99 USDT worth of BTC).
        Yet others can charge the fees for both buy and sell orders in the quote asset.
        """
        if order_candidate.order_side == TradeType.BUY:
            trading_pair = order_candidate.trading_pair
            price = order_candidate.price
            base, quote = split_hb_trading_pair(trading_pair)
            fee = self._exchange.get_fee(
                base,
                quote,
                order_candidate.order_type,
                order_candidate.order_side,
                order_candidate.amount,
                price,
            )
        else:
            fee = TradeFee(percent=Decimal("0"))

        return fee

    def _lock_available_collateral(self, order_candidate: OrderCandidate):
        self._locked_collateral[order_candidate.collateral_token] += order_candidate.collateral_amount
