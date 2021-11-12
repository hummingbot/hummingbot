from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional
from copy import copy

from hummingbot.connector import exchange_base
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.event.events import OrderType, TradeType


@dataclass
class OrderCandidate:
    trading_pair: str
    order_type: OrderType
    order_side: TradeType
    amount: Decimal
    price: Decimal
    collateral_amount: Optional[Decimal] = None
    collateral_token: Optional[str] = None
    leverage: Decimal = Decimal("1")


class BudgetChecker:
    def __init__(self, exchange: exchange_base.ExchangeBase):
        """
        Provides utilities for strategies to check if the required assets for trades are available.

        Used to determine if sufficient balance is available to place a set of strategy-proposed orders.
        The strategy can call `check_and_lock_available_collateral` for each one of the orders it intends to
        place. On each call, the `BudgetChecker` locks in the collateral amount needed for that order
        and makes it unavailable for the following hypothetical orders. Once the orders are sent to
        the exchange, the strategy must call `reset_locked_collateral` to free the hypothetically locked
        assets for the next set of checks.

        :param exchange: The exchange against which available collateral assets will be checked.
        """
        self._exchange = exchange
        self._locked_collateral: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    def reset_locked_collateral(self):
        """
        Frees collateral assets locked for hypothetical orders.
        """
        self._locked_collateral.clear()

    def adjust_candidates_and_lock_available_collateral(
        self, order_candidates: List[OrderCandidate], all_or_none: bool = True
    ) -> List[OrderCandidate]:
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

        :param order_candidate: The candidate order to check and adjust.
        :param all_or_none: Should the order amount be set to zero on insufficient balance.
        :return: The adjusted order candidate.
        """
        adjusted_candidate = self.adjust_candidate(
            order_candidate, all_or_none
        )
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
        if adjusted_candidate.collateral_amount < available_collateral:
            if all_or_none:
                adjusted_candidate.amount = Decimal("0")
                adjusted_candidate.collateral_amount = Decimal("0")
            else:
                adjusted_candidate = self._adjust_amounts(adjusted_candidate, available_collateral)
        return adjusted_candidate

    def populate_collateral_fields(self, order_candidate: OrderCandidate) -> OrderCandidate:
        """
        Populates the required collateral amount and the collateral token fields for the given order.

        This implementation assumes a spot-specific configuration for collaterals (i.e. the quote
        token for buy orders and base for sell). It can be overridden to provide other
        configurations such as in the case of perpetual connectors.

        :param order_candidate: The candidate order to check and adjust.
        :return: The adjusted order candidate.
        """
        trading_pair = order_candidate.trading_pair

        base, quote = split_hb_trading_pair(trading_pair)
        collateral_token = quote if TradeType.BUY else base

        required_collateral = order_candidate.amount * order_candidate.price
        adjustment = self._get_collateral_adjustment_for_fees(order_candidate)
        required_collateral += adjustment

        adjusted_candidate = copy(order_candidate)
        adjusted_candidate.collateral_amount = required_collateral
        adjusted_candidate.collateral_token = collateral_token

        return adjusted_candidate

    def _get_collateral_adjustment_for_fees(self, order_candidate: OrderCandidate) -> Decimal:
        """
        Returns the adjustment term for the required collateral amount due to fees.
        The return value (adjustment term) is intended to be added to the base collateral amount.

        Exchange-specific implementations of this class can override this method to model
        the exchange's exact fee structure.

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
            amount = order_candidate.amount
            base, quote = split_hb_trading_pair(trading_pair)
            fee = self._exchange.get_fee(
                base, quote, order_candidate.order_type, order_candidate.order_side, amount, price
            )
            fee_adjustment = fee.fee_amount_in_quote(trading_pair, price, amount)
        else:
            fee_adjustment = Decimal("0")
        return fee_adjustment

    def _lock_available_collateral(self, order_candidate: OrderCandidate):
        self._locked_collateral[order_candidate.collateral_token] += order_candidate.collateral_amount

    def _adjust_amounts(
        self, order_candidate: OrderCandidate, available_collateral: Decimal
    ) -> OrderCandidate:
        if order_candidate.order_side == TradeType.BUY:
            trading_pair = order_candidate.trading_pair
            base, quote = split_hb_trading_pair(trading_pair)
            fee = self._exchange.get_fee(
                base,
                quote,
                order_candidate.order_type,
                order_candidate.order_side,
                order_candidate.amount,
                order_candidate.price,
            )
            adjusted_amount = fee.order_amount_from_quote_with_fee(
                trading_pair, order_candidate.price, available_collateral
            )
            adjusted_amount = self._exchange.quantize_order_amount(trading_pair, adjusted_amount)
        else:
            adjusted_amount = available_collateral / order_candidate.price

        adjusted_candidate = copy(order_candidate)
        adjusted_candidate.amount = adjusted_amount
        adjusted_candidate.collateral_amount = available_collateral

        return adjusted_candidate


class PerpetualBudgetChecker(BudgetChecker):
    def __init__(self, exchange: exchange_base.ExchangeBase):
        """
        In the case of derived instruments, the collateral can be any token.
        To get this information, this class uses the `get_buy_collateral_token`
        and `get_sell_collateral_token` methods provided by the `PerpetualTrading` interface.
        """
        super().__init__(exchange)
        self._validate_perpetual_connector()

    def populate_collateral_fields(self, order_candidate: OrderCandidate) -> OrderCandidate:
        trading_pair = order_candidate.trading_pair

        if order_candidate.order_side == TradeType.BUY:
            collateral_token = await self._exchange.get_buy_collateral_token(trading_pair)
        else:
            collateral_token = await self._exchange.get_sell_collateral_token(trading_pair)

        order_size = order_candidate.amount * order_candidate.price
        required_collateral = order_size / order_candidate.leverage
        adjustment = self._get_collateral_adjustment_for_fees(order_candidate)
        required_collateral += adjustment

        adjusted_candidate = copy(order_candidate)
        adjusted_candidate.collateral_amount = required_collateral
        adjusted_candidate.collateral_token = collateral_token

        return adjusted_candidate

    def _validate_perpetual_connector(self):
        if not isinstance(self._exchange, PerpetualTrading):
            raise TypeError(
                f"{self.__class__} must be passed an exchange implementing the {PerpetualTrading} interface."
            )

    def _get_collateral_adjustment_for_fees(self, order_candidate: OrderCandidate) -> Decimal:
        trading_pair = order_candidate.trading_pair
        amount = order_candidate.amount
        price = order_candidate.price

        base, quote = split_hb_trading_pair(trading_pair)
        fee = self._exchange.get_fee(
            base, quote, order_candidate.order_type, order_candidate.order_side, amount, price
        )
        fee_adjustment = fee.fee_amount_in_quote(trading_pair, price, amount)

        return fee_adjustment

    def _adjust_amounts(
        self, order_candidate: OrderCandidate, available_collateral: Decimal
    ) -> OrderCandidate:
        trading_pair = order_candidate.trading_pair
        price = order_candidate.price

        base, quote = split_hb_trading_pair(trading_pair)
        if order_candidate.collateral_token not in [base, quote]:
            raise NotImplementedError(
                f"Cannot adjust the order amount if the collateral is neither of the order's"
                f" base or quote tokens. Base = {base}, quote = {quote}, collateral token ="
                f" {order_candidate.collateral_token}."
            )
        fee = self._exchange.get_fee(
            base,
            quote,
            order_candidate.order_type,
            order_candidate.order_side,
            order_candidate.amount,
            price,
        )
        adjusted_amount = fee.order_amount_from_quote_with_fee(
            trading_pair, price, available_collateral
        )
        adjusted_amount = self._exchange.quantize_order_amount(trading_pair, adjusted_amount)

        adjusted_candidate = copy(order_candidate)
        adjusted_candidate.amount = adjusted_amount
        adjusted_candidate.collateral_amount = available_collateral

        return adjusted_candidate
