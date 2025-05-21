from abc import ABC, abstractmethod
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

from xrpl.models import XRP, IssuedCurrencyAmount, Memo, OfferCreate, Path, PathStep, Payment, PaymentFlag, Transaction
from xrpl.utils import xrp_to_drops

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import convert_string_to_hex
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class XRPLOrderPlacementStrategy(ABC):
    """Abstract base class for XRPL order placement strategies"""

    def __init__(self, connector: "XrplExchange", order: InFlightOrder):
        self._connector = connector
        self._order = order

    @abstractmethod
    async def create_order_transaction(self) -> Transaction:
        """Create the appropriate transaction for the order type"""
        pass

    def get_base_quote_amounts(
        self, price: Optional[Decimal] = None
    ) -> Tuple[Union[str, IssuedCurrencyAmount], Union[str, IssuedCurrencyAmount]]:
        """Calculate the base and quote amounts for the order"""
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(self._order.trading_pair)
        trading_rule = self._connector._trading_rules[self._order.trading_pair]

        amount_in_base_quantum = Decimal(trading_rule.min_base_amount_increment)
        amount_in_quote_quantum = Decimal(trading_rule.min_quote_amount_increment)

        # Use price if provided, otherwise use order price
        effective_price = price if price is not None else self._order.price
        if effective_price is None:
            raise ValueError("Price must be provided either in the order or as a parameter")

        amount_in_base = Decimal(self._order.amount.quantize(amount_in_base_quantum, rounding=ROUND_DOWN))
        amount_in_quote = Decimal(
            (self._order.amount * effective_price).quantize(amount_in_quote_quantum, rounding=ROUND_DOWN)
        )

        # Handle precision for base and quote amounts
        total_digits_base = len(str(amount_in_base).split(".")[1]) + len(str(amount_in_base).split(".")[0])
        if total_digits_base > CONSTANTS.XRPL_MAX_DIGIT:  # XRPL_MAX_DIGIT
            adjusted_quantum = CONSTANTS.XRPL_MAX_DIGIT - len(str(amount_in_base).split(".")[0])
            amount_in_base = Decimal(amount_in_base.quantize(Decimal(f"1e-{adjusted_quantum}"), rounding=ROUND_DOWN))

        total_digits_quote = len(str(amount_in_quote).split(".")[1]) + len(str(amount_in_quote).split(".")[0])
        if total_digits_quote > CONSTANTS.XRPL_MAX_DIGIT:  # XRPL_MAX_DIGIT
            adjusted_quantum = CONSTANTS.XRPL_MAX_DIGIT - len(str(amount_in_quote).split(".")[0])
            amount_in_quote = Decimal(amount_in_quote.quantize(Decimal(f"1e-{adjusted_quantum}"), rounding=ROUND_DOWN))

        # Convert amounts based on currency type
        if self._order.trade_type is TradeType.SELL:
            if isinstance(base_currency, XRP):
                we_pay = xrp_to_drops(amount_in_base)
            else:
                we_pay = IssuedCurrencyAmount(
                    currency=base_currency.currency, issuer=base_currency.issuer, value=str(amount_in_base)
                )

            if isinstance(quote_currency, XRP):
                we_get = xrp_to_drops(amount_in_quote)
            else:
                we_get = IssuedCurrencyAmount(
                    currency=quote_currency.currency, issuer=quote_currency.issuer, value=str(amount_in_quote)
                )
        else:
            if isinstance(quote_currency, XRP):
                we_pay = xrp_to_drops(amount_in_quote)
            else:
                we_pay = IssuedCurrencyAmount(
                    currency=quote_currency.currency, issuer=quote_currency.issuer, value=str(amount_in_quote)
                )

            if isinstance(base_currency, XRP):
                we_get = xrp_to_drops(amount_in_base)
            else:
                we_get = IssuedCurrencyAmount(
                    currency=base_currency.currency, issuer=base_currency.issuer, value=str(amount_in_base)
                )

        return we_pay, we_get


class LimitOrderStrategy(XRPLOrderPlacementStrategy):
    """Strategy for placing limit orders"""

    async def create_order_transaction(self) -> Transaction:
        we_pay, we_get = self.get_base_quote_amounts()
        flags = self._connector.xrpl_order_type(self._order.order_type)

        flags += CONSTANTS.XRPL_SELL_FLAG

        memo = Memo(memo_data=convert_string_to_hex(self._order.client_order_id, padding=False))
        return OfferCreate(
            account=self._connector._xrpl_auth.get_account(),
            flags=flags,
            taker_gets=we_pay,
            taker_pays=we_get,
            memos=[memo],
        )


class MarketOrderStrategy(XRPLOrderPlacementStrategy):
    """Strategy for placing market orders"""

    async def create_order_transaction(self) -> Transaction:
        # Get best price from order book
        price = Decimal(
            await self._connector._get_best_price(
                self._order.trading_pair, is_buy=True if self._order.trade_type is TradeType.BUY else False
            )
        )

        # Add slippage to make sure we get the order filled
        if self._order.trade_type is TradeType.SELL:
            price *= Decimal("1") - CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE
        else:
            price *= Decimal("1") + CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE

        we_pay, we_get = self.get_base_quote_amounts(price)
        flags = self._connector.xrpl_order_type(self._order.order_type)

        flags += CONSTANTS.XRPL_SELL_FLAG

        memo = Memo(memo_data=convert_string_to_hex(self._order.client_order_id, padding=False))
        return OfferCreate(
            account=self._connector._xrpl_auth.get_account(),
            flags=flags,
            taker_gets=we_pay,
            taker_pays=we_get,
            memos=[memo],
        )


class AMMSwapOrderStrategy(XRPLOrderPlacementStrategy):
    """Strategy for placing AMM swap orders"""

    async def create_order_transaction(self) -> Transaction:
        # Get best price from order book
        price = Decimal(
            await self._connector._get_best_price(
                self._order.trading_pair, is_buy=True if self._order.trade_type is TradeType.BUY else False
            )
        )

        fee_rate_pct = self._connector._trading_pair_fee_rules[self._order.trading_pair].get(
            "amm_pool_fee", Decimal("0.0")
        )

        we_pay, we_get = self.get_base_quote_amounts(price)

        if self._order.trade_type is TradeType.BUY:
            # add slippage to we_get
            if isinstance(we_get, IssuedCurrencyAmount):
                we_get = IssuedCurrencyAmount(
                    currency=we_get.currency,
                    issuer=we_get.issuer,
                    value=str(Decimal(we_get.value) * Decimal("1") + fee_rate_pct),
                )
            else:
                we_get = str(int(Decimal(we_get) * Decimal("1") + fee_rate_pct))

            if isinstance(we_pay, IssuedCurrencyAmount):
                we_pay = IssuedCurrencyAmount(
                    currency=we_pay.currency,
                    issuer=we_pay.issuer,
                    value=str(Decimal(we_pay.value) * Decimal("1") + fee_rate_pct),
                )
            else:
                we_pay = str(int(Decimal(we_pay) * Decimal("1") + fee_rate_pct))
        else:
            we_pay, we_get = self.get_base_quote_amounts(price * Decimal(1 + fee_rate_pct))

        paths: Optional[List[Path]] = None

        # if both we_pay and we_get are not XRP:
        if isinstance(we_pay, IssuedCurrencyAmount) and isinstance(we_get, IssuedCurrencyAmount):
            path: Path = [
                PathStep(
                    account=we_pay.issuer,
                ),
                PathStep(
                    currency=we_get.currency,
                    issuer=we_get.issuer,
                ),
            ]
            paths = [path]

        # if we_pay is XRP, we_get must be an IssuedCurrencyAmount
        if isinstance(we_pay, str) and isinstance(we_get, IssuedCurrencyAmount):
            path: Path = [
                PathStep(
                    currency=we_get.currency,
                    issuer=we_get.issuer,
                ),
            ]
            paths = [path]

        # if we_pay is IssuedCurrencyAmount, we_get must be XRP
        if isinstance(we_pay, IssuedCurrencyAmount) and isinstance(we_get, str):
            path: Path = [
                PathStep(currency="XRP"),
            ]
            paths = [path]

        swap_amm_prefix = "AMM_SWAP"

        memo = Memo(memo_data=convert_string_to_hex(f"{self._order.client_order_id}_{swap_amm_prefix}", padding=False))

        return Payment(
            account=self._connector._xrpl_auth.get_account(),
            destination=self._connector._xrpl_auth.get_account(),
            amount=we_get,
            send_max=we_pay,
            paths=paths,
            memos=[memo],
            flags=PaymentFlag.TF_NO_RIPPLE_DIRECT + PaymentFlag.TF_PARTIAL_PAYMENT,
        )


class OrderPlacementStrategyFactory:
    """Factory for creating order placement strategies"""

    @staticmethod
    def create_strategy(connector: "XrplExchange", order: InFlightOrder) -> XRPLOrderPlacementStrategy:
        if order.order_type == OrderType.LIMIT or order.order_type == OrderType.LIMIT_MAKER:
            return LimitOrderStrategy(connector, order)
        elif order.order_type == OrderType.MARKET:
            return MarketOrderStrategy(connector, order)
        elif order.order_type == OrderType.AMM_SWAP:
            return AMMSwapOrderStrategy(connector, order)
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")
