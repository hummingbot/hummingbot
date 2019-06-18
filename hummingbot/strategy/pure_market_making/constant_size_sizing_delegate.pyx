from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase

from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class ConstantSizeSizingDelegate(OrderSizingDelegate):
    def __init__(self, order_size: float):
        super().__init__()
        self._order_size = order_size

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

        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
            else:
                has_active_ask = True

        return SizingProposal(
            ([bid_order_size]
             if quote_asset_balance > pricing_proposal.buy_order_prices[0] * bid_order_size and not has_active_bid
             else [0.0]),
            ([ask_order_size]
             if base_asset_balance > ask_order_size and not has_active_ask else
             [0.0])
        )