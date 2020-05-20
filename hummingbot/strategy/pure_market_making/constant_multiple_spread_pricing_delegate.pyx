from decimal import Decimal

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
from .data_types import PricingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class ConstantMultipleSpreadPricingDelegate(OrderPricingDelegate):
    def __init__(self, bid_spread: Decimal,
                 ask_spread: Decimal,
                 order_level_spread: Decimal,
                 order_levels: int):
        super().__init__()
        self._bid_spread = bid_spread
        self._ask_spread = ask_spread
        self._order_level_spread = order_level_spread
        self._order_levels = order_levels

    @property
    def bid_spread(self) -> Decimal:
        return self._bid_spread

    @bid_spread.setter
    def bid_spread(self, value):
        self._bid_spread = value

    @property
    def ask_spread(self) -> Decimal:
        return self._ask_spread

    @ask_spread.setter
    def ask_spread(self, value):
        self._ask_spread = value

    @property
    def order_levels(self) -> int:
        return self._order_levels

    @property
    def order_level_spread(self) -> Decimal:
        return self._order_level_spread

    cdef object c_get_order_price_proposal(self,
                                           PureMarketMakingStrategyV2 strategy,
                                           object market_info,  # MarketTradingPairTuple
                                           list active_orders,
                                           object asset_mid_price):
        cdef:
            MarketBase maker_market = market_info.market
            OrderBook maker_order_book = maker_market.c_get_order_book(market_info.trading_pair)
            str market_name = maker_market.name
            object mid_price = asset_mid_price
            list bid_prices = [maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                   mid_price * (Decimal(1) - self._bid_spread))]
            list ask_prices = [maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                   mid_price * (Decimal(1) + self._ask_spread))]

        for _ in range(self.order_levels - 1):
            last_bid_price = bid_prices[-1]
            current_bid_price = maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                    last_bid_price * (Decimal(1) - self.order_level_spread))
            bid_prices.append(current_bid_price)

            last_ask_price = ask_prices[-1]
            current_ask_price = maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                    last_ask_price * (Decimal(1) + self.order_level_spread))

            ask_prices.append(current_ask_price)

        return PricingProposal(bid_prices, ask_prices)
