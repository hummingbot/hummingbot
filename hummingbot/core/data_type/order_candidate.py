import typing
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderType, PositionAction, TradeType
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee, build_trade_fee

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase


@dataclass
class OrderCandidate:
    """
    WARNING: Do not use this class for sizing. Instead, use the `BudgetChecker`.

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
    percent_fee_value: Optional[TokenAmount] = field(default=None, init=False)
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

    def get_size_token_and_order_size(self) -> TokenAmount:
        trading_pair = self.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if self.order_side == TradeType.BUY:
            order_size = self.amount * self.price
            size_token = quote
        else:
            order_size = self.amount
            size_token = base
        return TokenAmount(size_token, order_size)

    def set_to_zero(self):
        self._scale_order(scaler=Decimal("0"))

    def populate_collateral_entries(self, exchange: 'ExchangeBase'):
        self._populate_order_collateral_entry(exchange)
        fee = self._get_fee(exchange)
        self._populate_percent_fee_collateral_entry(exchange, fee)
        self._populate_fixed_fee_collateral_entries(fee)
        self._populate_potential_returns_entry(exchange)
        self._populate_percent_fee_value(exchange, fee)
        self._apply_fee_impact_on_potential_returns(exchange, fee)

    def adjust_from_balances(self, available_balances: Dict[str, Decimal]):
        if not self.is_zero_order:
            self._adjust_for_order_collateral(available_balances)
        if not self.is_zero_order:
            self._adjust_for_percent_fee_collateral(available_balances)
        if not self.is_zero_order:
            self._adjust_for_fixed_fee_collaterals(available_balances)

    def _populate_order_collateral_entry(self, exchange: 'ExchangeBase'):
        oc_token = self._get_order_collateral_token(exchange)
        if oc_token is not None:
            oc_amount = self._get_order_collateral_amount(exchange, oc_token)
            self.order_collateral = TokenAmount(oc_token, oc_amount)

    def _get_order_collateral_token(self, exchange: 'ExchangeBase') -> Optional[str]:
        trading_pair = self.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if self.order_side == TradeType.BUY:
            oc_token = quote
        else:
            oc_token = base
        return oc_token

    def _get_order_collateral_amount(
        self, exchange: 'ExchangeBase', order_collateral_token: str
    ) -> Decimal:
        size_token, order_size = self.get_size_token_and_order_size()
        size_collateral_price = self._get_size_collateral_price(exchange, order_collateral_token)
        oc_amount = order_size * size_collateral_price
        return oc_amount

    def _populate_percent_fee_collateral_entry(self, exchange: 'ExchangeBase', fee: TradeFeeBase):
        impact = fee.get_fee_impact_on_order_cost(self, exchange)
        if impact is not None:
            token, amount = impact
            self.percent_fee_collateral = TokenAmount(token, amount)

    def _populate_fixed_fee_collateral_entries(self, fee: TradeFeeBase):
        self.fixed_fee_collaterals = []
        for token, amount in fee.flat_fees:
            self.fixed_fee_collaterals.append(
                TokenAmount(token, amount))

    def _populate_potential_returns_entry(self, exchange: 'ExchangeBase'):
        r_token = self._get_returns_token(exchange)
        if r_token is not None:
            r_amount = self._get_returns_amount(exchange)
            self.potential_returns = TokenAmount(r_token, r_amount)

    def _populate_percent_fee_value(self, exchange: 'ExchangeBase', fee: TradeFeeBase):
        cost_impact = fee.get_fee_impact_on_order_cost(self, exchange)
        if cost_impact is not None:
            self.percent_fee_value = cost_impact
        else:
            returns_impact = fee.get_fee_impact_on_order_returns(self, exchange)
            if returns_impact is not None:
                impact_token = self.potential_returns.token
                self.percent_fee_value = TokenAmount(impact_token, returns_impact)

    def _apply_fee_impact_on_potential_returns(self, exchange: 'ExchangeBase', fee: TradeFeeBase):
        if self.potential_returns is not None:
            impact = fee.get_fee_impact_on_order_returns(self, exchange)
            if impact is not None:
                self.potential_returns.amount -= impact

    def _get_returns_token(self, exchange: 'ExchangeBase') -> Optional[str]:
        trading_pair = self.trading_pair
        base, quote = split_hb_trading_pair(trading_pair)
        if self.order_side == TradeType.BUY:
            r_token = base
        else:
            r_token = quote
        return r_token

    def _get_returns_amount(self, exchange: 'ExchangeBase') -> Decimal:
        if self.order_side == TradeType.BUY:
            r_amount = self.amount
        else:
            r_amount = self.amount * self.price
        return r_amount

    def _get_size_collateral_price(
        self, exchange: 'ExchangeBase', order_collateral_token: str
    ) -> Decimal:
        size_token, _ = self.get_size_token_and_order_size()
        base, quote = split_hb_trading_pair(self.trading_pair)

        if order_collateral_token == size_token:
            price = Decimal("1")
        elif order_collateral_token == base:  # size_token == quote
            price = Decimal("1") / self.price
        elif order_collateral_token == quote:  # size_token == base
            price = self.price
        else:
            size_collateral_pair = combine_to_hb_trading_pair(size_token, order_collateral_token)
            price = exchange.get_price(size_collateral_pair, is_buy=True)  # we are buying

        return price

    def _adjust_for_order_collateral(self, available_balances: Dict[str, Decimal]):
        if self.order_collateral is not None:
            token, amount = self.order_collateral
            if available_balances[token] < amount:
                scaler = available_balances[token] / amount
                self._scale_order(scaler)

    def _adjust_for_percent_fee_collateral(self, available_balances: Dict[str, Decimal]):
        if self.percent_fee_collateral is not None:
            token, amount = self.percent_fee_collateral
            if token == self.order_collateral.token:
                amount += self.order_collateral.amount
            if available_balances[token] < amount:
                scaler = available_balances[token] / amount
                self._scale_order(scaler)

    def _adjust_for_fixed_fee_collaterals(self, available_balances: Dict[str, Decimal]):
        oc_token = self.order_collateral.token if self.order_collateral is not None else None
        pfc_token = self.percent_fee_collateral.token if self.percent_fee_collateral is not None else None
        oc_amount, pfc_amount = self._get_order_and_pf_collateral_amounts_for_ff_adjustment()

        for collateral_entry in self.fixed_fee_collaterals:
            ffc_token, ffc_amount = collateral_entry
            available_balance = available_balances[ffc_token]
            if available_balance < ffc_amount:
                self._scale_order(scaler=Decimal("0"))
                break
            if oc_token is not None and ffc_token == oc_token and available_balance < ffc_amount + oc_amount:
                scaler = (available_balance - ffc_amount) / oc_amount
                self._scale_order(scaler)
                oc_amount, pfc_amount = self._get_order_and_pf_collateral_amounts_for_ff_adjustment()
            if pfc_token is not None and ffc_token == pfc_token and available_balance < ffc_amount + pfc_amount:
                scaler = (available_balance - ffc_amount) / pfc_amount
                self._scale_order(scaler)
                oc_amount, pfc_amount = self._get_order_and_pf_collateral_amounts_for_ff_adjustment()
            if self.is_zero_order:
                break

    def _get_order_and_pf_collateral_amounts_for_ff_adjustment(self) -> TokenAmount:
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
        return TokenAmount(oc_amount, pfc_amount)

    def _get_fee(self, exchange: 'ExchangeBase') -> TradeFeeBase:
        trading_pair = self.trading_pair
        price = self.price
        base, quote = split_hb_trading_pair(trading_pair)
        fee = build_trade_fee(
            exchange.name,
            self.is_maker,
            base,
            quote,
            self.order_type,
            self.order_side,
            self.amount,
            price,
        )

        return fee

    def _scale_order(self, scaler: Decimal):
        self.amount *= scaler
        if self.order_collateral is not None:
            self.order_collateral.amount *= scaler
        if self.percent_fee_collateral is not None:
            self.percent_fee_collateral.amount *= scaler
        if self.percent_fee_value is not None:
            self.percent_fee_value.amount *= scaler
        if self.potential_returns is not None:
            self.potential_returns.amount *= scaler
        if self.is_zero_order:
            self.order_collateral = None
            self.percent_fee_collateral = None
            self.percent_fee_value = None
            self.fixed_fee_collaterals = []
            self.potential_returns = None
        self.resized = True


@dataclass
class PerpetualOrderCandidate(OrderCandidate):
    leverage: Decimal = Decimal("1")
    position_close: bool = False

    def _get_order_collateral_token(self, exchange: 'ExchangeBase') -> Optional[str]:
        if self.position_close:
            oc_token = None  # the contract is the collateral
        else:
            oc_token = self._get_collateral_token(exchange)
        return oc_token

    def _get_order_collateral_amount(
        self, exchange: 'ExchangeBase', order_collateral_token: str
    ) -> Decimal:
        if self.position_close:
            oc_amount = Decimal("0")  # the contract is the collateral
        else:
            oc_amount = self._get_collateral_amount(exchange)
        return oc_amount

    def _populate_percent_fee_collateral_entry(self, exchange: 'ExchangeBase', fee: TradeFeeBase):
        if not self.position_close:
            super()._populate_percent_fee_collateral_entry(exchange, fee)
            if (
                self.percent_fee_collateral is not None
                and self.percent_fee_collateral.token == self.order_collateral.token
            ):
                leverage = self.leverage
                self.percent_fee_collateral.amount *= leverage

    def _populate_percent_fee_value(self, exchange: 'ExchangeBase', fee: TradeFeeBase):
        if not self.position_close:
            super()._populate_percent_fee_value(exchange, fee)
            if (
                self.percent_fee_value is not None
                and self.percent_fee_value.token == self.order_collateral.token
            ):
                leverage = self.leverage
                self.percent_fee_value.amount *= leverage

    def _get_returns_token(self, exchange: 'ExchangeBase') -> Optional[str]:
        if self.position_close:
            r_token = self._get_collateral_token(exchange)
        else:
            r_token = None  # the contract is the returns
        return r_token

    def _get_returns_amount(self, exchange: 'ExchangeBase') -> Decimal:
        if self.position_close:
            r_amount = self._get_collateral_amount(exchange)
        else:
            r_amount = Decimal("0")  # the contract is the returns
        return r_amount

    def _get_collateral_amount(self, exchange: 'ExchangeBase') -> Decimal:
        if self.position_close:
            self._flip_order_side()
        size_token, order_size = self.get_size_token_and_order_size()
        if self.position_close:
            self._flip_order_side()
        order_token = self._get_collateral_token(exchange)
        size_collateral_price = self._get_size_collateral_price(exchange, order_token)
        amount = order_size * size_collateral_price / self.leverage
        return amount

    def _get_collateral_token(self, exchange: 'ExchangeBase') -> str:
        trading_pair = self.trading_pair
        if self.order_side == TradeType.BUY:
            token = exchange.get_buy_collateral_token(trading_pair)
        else:
            token = exchange.get_sell_collateral_token(trading_pair)
        return token

    def _flip_order_side(self):
        self.order_side = (
            TradeType.BUY if self.order_side == TradeType.SELL
            else TradeType.SELL
        )

    def _get_fee(self, exchange: 'ExchangeBase') -> TradeFeeBase:
        base, quote = split_hb_trading_pair(self.trading_pair)
        position_action = PositionAction.CLOSE if self.position_close else PositionAction.OPEN
        fee = build_perpetual_trade_fee(
            exchange.name,
            self.is_maker,
            position_action,
            base,
            quote,
            self.order_type,
            self.order_side,
            self.amount,
            self.price,
        )

        return fee
