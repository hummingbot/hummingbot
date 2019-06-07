from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase

from .data_types import PricingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class ConstantSpreadPricingDelegate(OrderPricingDelegate):
    def __init__(self, bid_spread: float, ask_spread: float):
        super().__init__()
        self._bid_spread = bid_spread
        self._ask_spread = ask_spread

    @property
    def bid_spread(self) -> float:
        return self._bid_spread

    @property
    def ask_spread(self) -> float:
        return self._ask_spread

    cdef object c_get_order_price_proposal(self,
                                           PureMarketMakingStrategyV2 strategy,
                                           object market_info,
                                           list active_orders):
        cdef:
            MarketBase maker_market = market_info.market
            OrderBook maker_order_book = maker_market.c_get_order_book(market_info.symbol)
            double top_bid_price = maker_order_book.c_get_price(False)
            double top_ask_price = maker_order_book.c_get_price(True)
            str market_name = maker_market.name
            double mid_price = (top_bid_price + top_ask_price) * 0.5

        return PricingProposal(mid_price * (1.0 - self._bid_spread),
                               mid_price * (1.0 + self._ask_spread))
