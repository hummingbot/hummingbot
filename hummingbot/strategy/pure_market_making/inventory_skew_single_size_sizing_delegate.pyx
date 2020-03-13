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
from .inventory_skew_calculator cimport c_calculate_bid_ask_ratios_from_base_asset_ratio

s_logger = None
s_decimal_0 = Decimal(0)


cdef class InventorySkewSingleSizeSizingDelegate(OrderSizingDelegate):

    def __init__(self,
                 order_size: Decimal,
                 inventory_target_base_percent: Optional[Decimal] = None,
                 base_asset_range: Optional[Decimal] = None):
        super().__init__()
        self._order_size = order_size
        self._inventory_target_base_percent = inventory_target_base_percent
        self._base_asset_range = base_asset_range if base_asset_range is not None else order_size * Decimal(2)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @property
    def order_size(self) -> Decimal:
        return self._order_size

    @property
    def inventory_target_base_ratio(self) -> Decimal:
        return self._inventory_target_base_percent

    @property
    def inventory_target_base_range(self) -> Decimal:
        return self._base_asset_range

    cdef object c_get_order_size_proposal(self,
                                          PureMarketMakingStrategyV2 strategy,
                                          object market_info,
                                          list active_orders,
                                          object pricing_proposal):
        cdef:
            MarketBase market = market_info.market
            str trading_pair = market_info.trading_pair
            object buy_fees
            object base_asset_balance = Decimal(market.c_get_available_balance(market_info.base_asset))
            object quote_asset_balance = Decimal(market.c_get_available_balance(market_info.quote_asset))
            object top_bid_price = market.c_get_price(trading_pair, False)
            object top_ask_price = market.c_get_price(trading_pair, True)
            object mid_price = (top_bid_price + top_ask_price) * Decimal("0.5")
            object bid_order_size = self._order_size
            object ask_order_size = self._order_size
            object quantized_bid_order_size
            object quantized_ask_order_size
            bint has_active_bid = False
            bint has_active_ask = False
            object required_quote_asset_balance

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
            bid_ask_ratios = c_calculate_bid_ask_ratios_from_base_asset_ratio(
                float(base_asset_balance),
                float(quote_asset_balance),
                float(mid_price),
                float(self._inventory_target_base_percent),
                float(self._base_asset_range)
            )
            bid_order_size = Decimal(bid_ask_ratios.bid_ratio) * bid_order_size
            ask_order_size = Decimal(bid_ask_ratios.ask_ratio) * ask_order_size

        if market.name == "binance":
            quantized_bid_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      bid_order_size,
                                                                      pricing_proposal.buy_order_prices[0])
            quantized_ask_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      ask_order_size,
                                                                      pricing_proposal.sell_order_prices[0])
            required_quote_asset_balance = pricing_proposal.buy_order_prices[0] * quantized_bid_order_size

        else:
            quantized_bid_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      bid_order_size)
            quantized_ask_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      ask_order_size)

            buy_fees = market.c_get_fee(market_info.base_asset,
                                        market_info.quote_asset,
                                        OrderType.MARKET, TradeType.BUY,
                                        quantized_bid_order_size,
                                        pricing_proposal.buy_order_prices[0])

            required_quote_asset_balance = (pricing_proposal.buy_order_prices[0] *
                                            (Decimal(1) + buy_fees.percent) *
                                            quantized_bid_order_size)

        if quote_asset_balance < required_quote_asset_balance:
            bid_order_size = quote_asset_balance / pricing_proposal.buy_order_prices[0]
            quantized_bid_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      bid_order_size,
                                                                      pricing_proposal.buy_order_prices[0])

        if base_asset_balance < quantized_ask_order_size:
            quantized_ask_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      base_asset_balance,
                                                                      pricing_proposal.sell_order_prices[0])

        return SizingProposal(
            ([quantized_bid_order_size] if not has_active_bid else [s_decimal_0]),
            ([quantized_ask_order_size] if not has_active_ask else [s_decimal_0])
        )
