from decimal import Decimal
import logging
from typing import Optional

from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.logger import HummingbotLogger
from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2

s_logger = None
s_decimal_0 = Decimal(0)


cdef class InventorySkewMultipleSizeSizingDelegate(OrderSizingDelegate):
    def __init__(self,
                 order_start_size: Decimal,
                 order_step_size: Decimal,
                 number_of_orders: int,
                 inventory_target_base_percent: Optional[Decimal] = None):
        super().__init__()
        self._order_start_size = order_start_size
        self._order_step_size = order_step_size
        self._number_of_orders = number_of_orders
        self._inventory_target_base_percent = inventory_target_base_percent

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @property
    def order_start_size(self) -> Decimal:
        return self._order_start_size

    @property
    def order_step_size(self) -> Decimal:
        return self._order_step_size

    @property
    def number_of_orders(self) -> int:
        return self._number_of_orders

    cdef object c_get_order_size_proposal(self,
                                          PureMarketMakingStrategyV2 strategy,
                                          object market_info,
                                          list active_orders,
                                          object pricing_proposal):
        cdef:
            MarketBase market = market_info.market
            str trading_pair = market_info.trading_pair
            object base_asset_balance = market.c_get_available_balance(market_info.base_asset)
            object quote_asset_balance = market.c_get_available_balance(market_info.quote_asset)
            object current_quote_asset_order_size_total = s_decimal_0
            object quote_asset_order_size
            object current_base_asset_order_size_total = s_decimal_0
            object top_bid_price
            object top_ask_price
            object mid_price
            object total_base_asset_quote_value
            object total_quote_asset_quote_value
            object current_base_percent
            object current_quote_percent
            object target_base_percent
            object target_quote_percent
            object current_target_base_ratio
            object current_target_quote_ratio
            bint has_active_bid = False
            bint has_active_ask = False
            list buy_orders = []
            list sell_orders = []
            current_bid_order_size
            current_ask_order_size

        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
                quote_asset_balance += active_order.quantity * active_order.price
            else:
                has_active_ask = True
                base_asset_balance += active_order.quantity

        if has_active_bid and has_active_ask:
            return SizingProposal([s_decimal_0], [s_decimal_0])

        if self._inventory_target_base_percent is not None:
            top_bid_price = market.c_get_price(trading_pair, False)
            top_ask_price = market.c_get_price(trading_pair, True)
            mid_price = (top_bid_price + top_ask_price) / Decimal(2)

            total_base_asset_quote_value = base_asset_balance * mid_price
            total_quote_asset_quote_value = quote_asset_balance
            total_quote_value = total_base_asset_quote_value + total_quote_asset_quote_value

            if total_quote_value == s_decimal_0:
                return SizingProposal([s_decimal_0], [s_decimal_0])

            # Calculate percent value of base and quote
            current_base_percent = total_base_asset_quote_value / total_quote_value
            current_quote_percent = total_quote_asset_quote_value / total_quote_value

            target_base_percent = self._inventory_target_base_percent
            target_quote_percent = Decimal(1) - target_base_percent

            # Calculate target ratio based on current percent vs. target percent
            current_target_base_ratio = current_base_percent / target_base_percent \
                if target_base_percent > s_decimal_0 else s_decimal_0
            current_target_quote_ratio = current_quote_percent / target_quote_percent \
                if target_quote_percent > s_decimal_0 else s_decimal_0

            # By default 100% of order size is on both sides, therefore adjusted ratios should be 2 (100% + 100%).
            # If target base percent is 0 (0%) target quote ratio is 200%.
            # If target base percent is 1 (100%) target base ratio is 200%.
            if current_target_base_ratio > Decimal(1) or current_target_quote_ratio == s_decimal_0:
                current_target_base_ratio = Decimal(2) - current_target_quote_ratio
            else:
                current_target_quote_ratio = Decimal(2) - current_target_base_ratio

        for i in range(self.number_of_orders):
            current_bid_order_size = (self.order_start_size + self.order_step_size * i) * current_target_quote_ratio
            current_ask_order_size = (self.order_start_size + self.order_step_size * i) * current_target_base_ratio
            if market.name == "binance":
                # For binance fees is calculated in base token, so need to adjust for that
                quantized_bid_order_size = market.c_quantize_order_amount(
                    market_info.trading_pair,
                    current_bid_order_size,
                    pricing_proposal.buy_order_prices[i]
                )
                # Check whether you have enough quote tokens
                quote_asset_order_size = quantized_bid_order_size * pricing_proposal.buy_order_prices[i]
                if quote_asset_balance < current_quote_asset_order_size_total + quote_asset_order_size:
                    quote_asset_order_size = quote_asset_balance - current_quote_asset_order_size_total
                    bid_order_size = quote_asset_order_size / pricing_proposal.buy_order_prices[i]
                    quantized_bid_order_size = market.c_quantize_order_amount(
                        market_info.trading_pair,
                        bid_order_size,
                        pricing_proposal.buy_order_prices[i]
                    )

            else:
                quantized_bid_order_size = market.c_quantize_order_amount(
                    market_info.trading_pair,
                    current_bid_order_size
                )
                buy_fees = market.c_get_fee(
                    market_info.base_asset,
                    market_info.quote_asset,
                    OrderType.MARKET,
                    TradeType.BUY,
                    quantized_bid_order_size,
                    pricing_proposal.buy_order_prices[i]
                )
                # For other exchanges, fees is calculated in quote tokens, so need to ensure you have enough for order + fees
                quote_asset_order_size = quantized_bid_order_size * pricing_proposal.buy_order_prices[i] * (Decimal(1) + buy_fees.percent)
                if quote_asset_balance < current_quote_asset_order_size_total + quote_asset_order_size:
                    quote_asset_order_size = quote_asset_balance - current_quote_asset_order_size_total
                    bid_order_size = quote_asset_order_size / pricing_proposal.buy_order_prices[i] * (Decimal(1) - buy_fees.percent)
                    quantized_bid_order_size = market.c_quantize_order_amount(
                        market_info.trading_pair,
                        bid_order_size,
                        pricing_proposal.buy_order_prices[i]
                    )
            current_quote_asset_order_size_total += quote_asset_order_size

            quantized_ask_order_size = market.c_quantize_order_amount(
                market_info.trading_pair,
                current_ask_order_size,
                pricing_proposal.sell_order_prices[i]
            )
            if base_asset_balance < current_base_asset_order_size_total + quantized_ask_order_size:
                quantized_ask_order_size = market.c_quantize_order_amount(
                    market_info.trading_pair,
                    base_asset_balance - current_base_asset_order_size_total,
                    pricing_proposal.sell_order_prices[i]
                )

            current_base_asset_order_size_total += quantized_ask_order_size
            if quantized_bid_order_size > s_decimal_0:
                buy_orders.append(quantized_bid_order_size)
            if quantized_ask_order_size > s_decimal_0:
                sell_orders.append(quantized_ask_order_size)

        return SizingProposal(
            buy_orders if not has_active_bid and len(buy_orders) > 0 else [s_decimal_0],
            sell_orders if not has_active_ask and len(sell_orders) > 0 else [s_decimal_0]
        )
