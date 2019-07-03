from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
from hummingbot.core.event.events import (
OrderType,
TradeType,
TradeFee
)
from typing import Optional
import logging

from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2
from hummingbot.logger import HummingbotLogger

s_logger:Optional[HummingbotLogger] = None

cdef class ConstantSizeSizingDelegate(OrderSizingDelegate):

    def __init__(self, order_size: float):
        super().__init__()
        self._order_size = order_size
        self._log_warning_order_size = True
        self._log_warning_balance = True

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @property
    def order_size(self) -> float:
        return self._order_size

    cdef object c_get_order_size_proposal(self,
                                          PureMarketMakingStrategyV2 strategy,
                                          object market_info,
                                          list active_orders,
                                          object pricing_proposal):
        cdef:
            MarketBase market = market_info.market
            object buy_fees
            double base_asset_balance = market.c_get_balance(market_info.base_currency)
            double quote_asset_balance = market.c_get_balance(market_info.quote_currency)
            double bid_order_size = self._order_size
            double ask_order_size = self._order_size
            bint has_active_bid = False
            bint has_active_ask = False

        buy_fees = market.c_get_fee(market_info.base_currency, market_info.quote_currency,
                                    OrderType.MARKET, TradeType.BUY,
                                    bid_order_size, pricing_proposal.buy_order_prices[0])

        if market.name == "binance":
            bid_order_size = market.c_quantize_order_amount(market_info.symbol, (self.order_size * (1+buy_fees.percent)), pricing_proposal.buy_order_prices[0])
            ask_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size, pricing_proposal.sell_order_prices[0])
            required_quote_asset_balance = pricing_proposal.buy_order_prices[0] * bid_order_size

        else:
            bid_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size)
            ask_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size)
            required_quote_asset_balance = pricing_proposal.buy_order_prices[0] * (1+float(buy_fees.percent)) * bid_order_size

        if self._log_warning_order_size:

            if (bid_order_size ==0):
                self.logger().network(f"Buy(bid) order size is less than minimum order size. Buy order will not be placed",
                                      f"The order size is too small for the market for buy order. Check order size in configuration.")
                #After warning once, set warning flag to False
                self._log_warning_order_size = False

            if (ask_order_size ==0):
                 self.logger().network(f"Sell(ask) order size is less than minimum order size. Sell order will not be placed",
                                       f"The order size is too small for the market for sell order. Check order size in configuration.")
                 #After warning once, set warning flag to False
                 self._log_warning_order_size = False


        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
            else:
                has_active_ask = True

        if self._log_warning_balance:

            if quote_asset_balance < required_quote_asset_balance:
                self.logger().network(f"Buy(bid) order is not placed because there is not enough Quote asset. "
                                      f"Quote Asset: {quote_asset_balance}, Price: {pricing_proposal.buy_order_prices[0]},"
                                      f"Size: {bid_order_size}",
                                      f"Not enough asset to place the required buy(bid) order. Check balances.")
                #After warning once, set warning flag to False
                self._log_warning_balance = False

            if (base_asset_balance < ask_order_size):
                self.logger().network(f"Sell(ask) order is not placed because there is not enough Base asset. "
                                      f"Base Asset: {base_asset_balance}, Size: {ask_order_size}",
                                      f"Not enough asset to place the required sell(ask) order. Check balances.")
                #After warning once, set warning flag to False
                self._log_warning_balance = False


        #Reset warning flag for balances if there is enough balance to place orders
        if (quote_asset_balance >= required_quote_asset_balance) and \
                (base_asset_balance >= ask_order_size):
            self._log_warning_balance = True

        #Reset warning flag for order size if both order sizes are greater than zero
        if bid_order_size >0 and ask_order_size>0:
            self._log_warning_order_size = True

        return SizingProposal(
            ([bid_order_size]
             if quote_asset_balance >= required_quote_asset_balance and not has_active_bid
             else [0.0]),
            ([ask_order_size]
             if base_asset_balance >= ask_order_size and not has_active_ask else
             [0.0])
        )