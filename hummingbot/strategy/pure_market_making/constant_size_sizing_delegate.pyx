from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
import logging

from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2

s_logger = None

cdef class ConstantSizeSizingDelegate(OrderSizingDelegate):
    def __init__(self, order_size: float):
        super().__init__()
        self._order_size = order_size

    @classmethod
    def logger(cls):
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
            double base_asset_balance = market.c_get_balance(market_info.base_currency)
            double quote_asset_balance = market.c_get_balance(market_info.quote_currency)
            double bid_order_size = self._order_size
            double ask_order_size = self._order_size
            bint has_active_bid = False
            bint has_active_ask = False

        if market.name == "binance":
            bid_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size, pricing_proposal.buy_order_prices[0])
            ask_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size, pricing_proposal.sell_order_prices[0])

        else:
            bid_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size)
            ask_order_size = market.c_quantize_order_amount(market_info.symbol, self.order_size)

        if (bid_order_size ==0):
            self.logger().warning(f"Buy(bid) order size is less than minimum order size. Buy order will not be placed")

        if (ask_order_size ==0):
             self.logger().warning(f"Sell(ask) order size is less than minimum order size. Sell order will not be placed")


        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
            else:
                has_active_ask = True

        if (quote_asset_balance < pricing_proposal.buy_order_prices[0] * bid_order_size):
            self.logger().warning(f"Not enough asset to place the required buy(bid) order. Check balances.")

        if (base_asset_balance < ask_order_size):
            self.logger().warning(f"Not enough asset to place the required sell(ask) order. Check balances.")

        return SizingProposal(
            ([bid_order_size]
             if quote_asset_balance >= pricing_proposal.buy_order_prices[0] * bid_order_size and not has_active_bid
             else [0.0]),
            ([ask_order_size]
             if base_asset_balance >= ask_order_size and not has_active_ask else
             [0.0])
        )