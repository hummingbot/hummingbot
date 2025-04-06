import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

s_decimal_nan = Decimal("NaN")
s_decimal_0 = Decimal("0")
arbprop_logger: Optional[HummingbotLogger] = None


@dataclass
class ArbProposalSide:
    """
    An arbitrage proposal side which contains info needed for order submission.
    """
    market_info: MarketTradingPairTuple
    is_buy: bool
    quote_price: Decimal
    order_price: Decimal
    amount: Decimal
    extra_flat_fees: List[TokenAmount]
    completed_event: asyncio.Event = asyncio.Event()
    failed_event: asyncio.Event = asyncio.Event()

    def __repr__(self):
        side = "buy" if self.is_buy else "sell"
        return f"Connector: {self.market_info.market.display_name}  Side: {side}  Quote Price: {self.quote_price}  " \
               f"Order Price: {self.order_price}  Amount: {self.amount}  Extra Fees: {self.extra_flat_fees}"

    @property
    def is_completed(self) -> bool:
        return self.completed_event.is_set()

    @property
    def is_failed(self) -> bool:
        return self.failed_event.is_set()

    def set_completed(self):
        self.completed_event.set()

    def set_failed(self):
        self.failed_event.set()


class ArbProposal:
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global arbprop_logger
        if arbprop_logger is None:
            arbprop_logger = logging.getLogger(__name__)
        return arbprop_logger

    """
    An arbitrage proposal which contains 2 sides of the proposal - one buy and one sell.
    """
    def __init__(self, first_side: ArbProposalSide, second_side: ArbProposalSide):
        if first_side.is_buy == second_side.is_buy:
            raise Exception("first_side and second_side must be on different side of buy and sell.")
        self.first_side: ArbProposalSide = first_side
        self.second_side: ArbProposalSide = second_side

    @property
    def has_failed_orders(self) -> bool:
        return any([self.first_side.is_failed, self.second_side.is_failed])

    def profit_pct(
            self,
            rate_source: Optional[RateOracle] = None,
            account_for_fee: bool = False,
    ) -> Decimal:
        """
        Returns a profit in percentage value (e.g. 0.01 for 1% profitability)
        Assumes the base token is the same in both arbitrage sides
        """
        if not rate_source:
            rate_source = RateOracle.get_instance()

        buy_side: ArbProposalSide = self.first_side if self.first_side.is_buy else self.second_side
        sell_side: ArbProposalSide = self.first_side if not self.first_side.is_buy else self.second_side
        base_conversion_pair: str = f"{sell_side.market_info.base_asset}-{buy_side.market_info.base_asset}"
        quote_conversion_pair: str = f"{sell_side.market_info.quote_asset}-{buy_side.market_info.quote_asset}"

        sell_base_to_buy_base_rate: Decimal = Decimal(1)
        sell_quote_to_buy_quote_rate: Decimal = rate_source.get_pair_rate(quote_conversion_pair)

        buy_fee_amount: Decimal = s_decimal_0
        sell_fee_amount: Decimal = s_decimal_0
        result: Decimal = s_decimal_0

        if sell_quote_to_buy_quote_rate and sell_base_to_buy_base_rate:
            if account_for_fee:
                buy_trade_fee: TradeFeeBase = build_trade_fee(
                    exchange=buy_side.market_info.market.name,
                    is_maker=False,
                    base_currency=buy_side.market_info.base_asset,
                    quote_currency=buy_side.market_info.quote_asset,
                    order_type=OrderType.MARKET,
                    order_side=TradeType.BUY,
                    amount=buy_side.amount,
                    price=buy_side.order_price,
                    extra_flat_fees=buy_side.extra_flat_fees
                )
                sell_trade_fee: TradeFeeBase = build_trade_fee(
                    exchange=sell_side.market_info.market.name,
                    is_maker=False,
                    base_currency=sell_side.market_info.base_asset,
                    quote_currency=sell_side.market_info.quote_asset,
                    order_type=OrderType.MARKET,
                    order_side=TradeType.SELL,
                    amount=sell_side.amount,
                    price=sell_side.order_price,
                    extra_flat_fees=sell_side.extra_flat_fees
                )
                buy_fee_amount: Decimal = buy_trade_fee.fee_amount_in_token(
                    trading_pair=buy_side.market_info.trading_pair,
                    price=buy_side.quote_price,
                    order_amount=buy_side.amount,
                    token=buy_side.market_info.quote_asset,
                    rate_source=rate_source
                )
                sell_fee_amount: Decimal = sell_trade_fee.fee_amount_in_token(
                    trading_pair=sell_side.market_info.trading_pair,
                    price=sell_side.quote_price,
                    order_amount=sell_side.amount,
                    token=sell_side.market_info.quote_asset,
                    rate_source=rate_source
                )

            buy_spent_net: Decimal = (buy_side.amount * buy_side.quote_price) + buy_fee_amount
            sell_gained_net: Decimal = (sell_side.amount * sell_side.quote_price) - sell_fee_amount
            sell_gained_net_in_buy_quote_currency: Decimal = (
                sell_gained_net * sell_quote_to_buy_quote_rate / sell_base_to_buy_base_rate
            )

            result: Decimal = (
                ((sell_gained_net_in_buy_quote_currency - buy_spent_net) / buy_spent_net)
                if buy_spent_net != s_decimal_0
                else s_decimal_0
            )
        else:
            self.logger().warning("The arbitrage proposal profitability could not be calculated due to a missing rate"
                                  f" ({base_conversion_pair}={sell_base_to_buy_base_rate},"
                                  f" {quote_conversion_pair}={sell_quote_to_buy_quote_rate})")
        return result

    def __repr__(self):
        return f"First Side - {self.first_side}\nSecond Side - {self.second_side}"

    def copy(self):
        return ArbProposal(
            ArbProposalSide(self.first_side.market_info, self.first_side.is_buy,
                            self.first_side.quote_price, self.first_side.order_price,
                            self.first_side.amount, self.first_side.extra_flat_fees),
            ArbProposalSide(self.second_side.market_info, self.second_side.is_buy,
                            self.second_side.quote_price, self.second_side.order_price,
                            self.second_side.amount, self.second_side.extra_flat_fees)
        )

    async def wait(self):
        return await safe_gather(*[self.first_side.completed_event.wait(), self.second_side.completed_event.wait()])
