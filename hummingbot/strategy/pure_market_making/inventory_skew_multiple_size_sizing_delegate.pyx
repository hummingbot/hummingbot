from decimal import Decimal
import logging
from typing import Optional

from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)
from hummingbot.logger import HummingbotLogger

from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2

s_logger = None
s_decimal_0 = Decimal(0)


cdef class InventorySkewMultipleSizeSizingDelegate(OrderSizingDelegate):
    def __init__(self,
                 order_start_size: float,
                 order_step_size:float,
                 number_of_orders:int,
                 inventory_target_base_percent: Optional[float] = None):
        super().__init__()
        self._order_start_size = order_start_size
        self._order_step_size = order_step_size
        self._number_of_orders = number_of_orders
        self._inventory_target_base_percent = inventory_target_base_percent
        self._log_warning_order_size = True
        self._log_warning_balance = True

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @property
    def order_start_size(self) -> float:
        return self._order_start_size

    @property
    def order_step_size(self) -> float:
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
            double base_asset_balance = market.c_get_available_balance(market_info.base_asset)
            double quote_asset_balance = market.c_get_available_balance(market_info.quote_asset)
            double required_quote_asset_balance = 0
            double required_base_asset_balance = 0
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
                quote_asset_balance += float(active_order.quantity) * float(active_order.price)
            else:
                has_active_ask = True
                base_asset_balance += float(active_order.quantity)

        if self._inventory_target_base_percent is not None:
            top_bid_price = Decimal(market.c_get_price(trading_pair, False))
            top_ask_price = Decimal(market.c_get_price(trading_pair, True))
            mid_price = (top_bid_price + top_ask_price) / 2
            total_base_asset_quote_value = Decimal(base_asset_balance) * mid_price
            total_quote_asset_quote_value = Decimal(quote_asset_balance)
            current_base_percent = total_base_asset_quote_value / (total_base_asset_quote_value + total_quote_asset_quote_value)
            current_quote_percent = total_quote_asset_quote_value / (total_base_asset_quote_value + total_quote_asset_quote_value)
            target_base_percent = Decimal(str(self._inventory_target_base_percent))
            target_quote_percent = 1 - target_base_percent
            current_target_base_ratio = current_base_percent / target_base_percent
            current_target_quote_ratio = current_quote_percent / target_quote_percent
            if current_target_base_ratio > 1:
                current_target_base_ratio = 2 - current_target_quote_ratio
            else:
                current_target_quote_ratio = 2 - current_target_base_ratio


        for idx in range(self.number_of_orders):
            current_bid_order_size = Decimal(self.order_start_size + self.order_step_size * idx)
            current_ask_order_size = Decimal(self.order_start_size + self.order_step_size * idx)

            current_bid_order_size *= current_target_quote_ratio
            current_ask_order_size *= current_target_base_ratio

            if market.name == "binance":
                # For binance fees is calculated in base token, so need to adjust for that
                quantized_buy_order_size = market.c_quantize_order_amount(market_info.trading_pair, current_bid_order_size, pricing_proposal.buy_order_prices[idx])
                # Check whether you have enough quote tokens
                required_quote_asset_balance += (float(quantized_buy_order_size) * float(pricing_proposal.buy_order_prices[idx]))

            else:
                quantized_buy_order_size = market.c_quantize_order_amount(market_info.trading_pair, current_bid_order_size)
                buy_fees = market.c_get_fee(market_info.base_asset, market_info.quote_asset,
                        OrderType.MARKET, TradeType.BUY,
                        current_bid_order_size, pricing_proposal.buy_order_prices[idx])
                # For other exchanges, fees is calculated in quote tokens, so need to ensure you have enough for order + fees
                required_quote_asset_balance += (float(quantized_buy_order_size) * float(pricing_proposal.buy_order_prices[idx]) * (1 + float(buy_fees.percent)))

            quantized_sell_order_size = market.c_quantize_order_amount(market_info.trading_pair, current_ask_order_size, pricing_proposal.sell_order_prices[idx])
            required_base_asset_balance += float(quantized_sell_order_size)
            if self._log_warning_order_size:
                if quantized_buy_order_size == 0 :
                    self.logger().network(f"Buy Order size is less than minimum order size for Price: {pricing_proposal.buy_order_prices[idx]} ",
                                          f"The orders for price of {pricing_proposal.buy_order_prices[idx]} are too small for the market. Check configuration")

                    #After warning once, set warning flag to False
                    self._log_warning_order_size = False

                if quantized_sell_order_size == 0 :
                    self.logger().network(f"Sell Order size is less than minimum order size for Price: {pricing_proposal.sell_order_prices[idx]} ",
                                          f"The orders for price of {pricing_proposal.sell_order_prices[idx]} are too small for the market. Check configuration")

                    #After warning once, set warning flag to False
                    self._log_warning_order_size = False

            buy_orders.append(quantized_buy_order_size)
            sell_orders.append(quantized_sell_order_size)

        #Reset warnings for order size if there are no zero sized orders in buy and sell
        if 0 not in buy_orders and 0 not in sell_orders:
            self._log_warning_order_size = True

        return SizingProposal(
            (buy_orders
             if quote_asset_balance >= required_quote_asset_balance and not has_active_bid
             else [s_decimal_0]),
            (sell_orders
             if base_asset_balance >= required_base_asset_balance and not has_active_ask else
             [s_decimal_0])
        )