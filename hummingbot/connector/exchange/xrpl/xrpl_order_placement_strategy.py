from abc import ABC, abstractmethod
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Optional, Tuple, Union

from xrpl.models import XRP, IssuedCurrencyAmount, Memo, OfferCreate, Transaction
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

    async def get_base_quote_amounts(
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
        we_pay, we_get = await self.get_base_quote_amounts()
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

        we_pay, we_get = await self.get_base_quote_amounts(price)
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
        # TODO: Implement AMM swap order logic
        # This will be similar to market order but use different transaction type
        raise NotImplementedError("AMM swap orders not yet implemented")


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
