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
from .inventory_skew_calculator cimport c_calculate_bid_ask_ratios_from_base_asset_ratio
from .inventory_skew_calculator import calculate_total_order_size
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_1 = Decimal(1)


cdef class InventorySkewMultipleSizeSizingDelegate(OrderSizingDelegate):
    def __init__(self,
                 order_start_size: Decimal,
                 order_step_size: Decimal,
                 order_levels: int,
                 inventory_target_base_percent: Optional[Decimal] = None,
                 inventory_range_multiplier: Optional[Decimal] = s_decimal_1):
        super().__init__()
        self._order_start_size = order_start_size
        self._order_step_size = order_step_size
        self._order_levels = order_levels
        self._inventory_target_base_percent = inventory_target_base_percent
        self._inventory_range_multiplier = inventory_range_multiplier

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
    def order_levels(self) -> int:
        return self._order_levels

    @property
    def inventory_target_base_ratio(self) -> Decimal:
        return self._inventory_target_base_percent

    @property
    def inventory_range_multiplier(self) -> Decimal:
        return self._inventory_range_multiplier

    @property
    def total_order_size(self) -> Decimal:
        return calculate_total_order_size(
            self._order_start_size,
            self._order_step_size,
            self._order_levels
        )

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
            object top_bid_price = market.c_get_price(trading_pair, False)
            object top_ask_price = market.c_get_price(trading_pair, True)
            object mid_price = (top_bid_price + top_ask_price) * Decimal("0.5")
            object quote_asset_order_size
            object current_quote_asset_order_size_total = s_decimal_0
            object current_base_asset_order_size_total = s_decimal_0
            bint has_active_bid = False
            bint has_active_ask = False
            list buy_orders = []
            list sell_orders = []

        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
                quote_asset_balance += active_order.quantity * active_order.price
            else:
                has_active_ask = True
                base_asset_balance += active_order.quantity

        if has_active_bid and has_active_ask:
            return SizingProposal([s_decimal_0], [s_decimal_0])

        cdef:
            object bid_adjustment_ratio
            object ask_adjustment_ratio
            object current_bid_order_size
            object current_ask_order_size

        if self._inventory_target_base_percent is not None:
            total_order_size = self.total_order_size
            bid_ask_ratios = c_calculate_bid_ask_ratios_from_base_asset_ratio(
                float(base_asset_balance),
                float(quote_asset_balance),
                float(mid_price),
                float(self._inventory_target_base_percent),
                float(total_order_size * self._inventory_range_multiplier)
            )
            bid_adjustment_ratio = Decimal(bid_ask_ratios.bid_ratio)
            ask_adjustment_ratio = Decimal(bid_ask_ratios.ask_ratio)

        for i in range(self.order_levels):
            current_bid_order_size = (self.order_start_size + self.order_step_size * i) * bid_adjustment_ratio
            current_ask_order_size = (self.order_start_size + self.order_step_size * i) * ask_adjustment_ratio
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
