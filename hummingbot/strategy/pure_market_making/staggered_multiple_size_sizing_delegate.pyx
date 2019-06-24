from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
import logging

from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2
from hummingbot.logger import HummingbotLogger


s_logger: Optional[HummingbotLogger] = None

cdef class StaggeredMultipleSizeSizingDelegate(OrderSizingDelegate):

    def __init__(self, order_start_size: float,
                 order_step_size:float,
                 number_of_orders:int):
        super().__init__()
        self._order_start_size = order_start_size
        self._order_step_size = order_step_size
        self._number_of_orders = number_of_orders

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
            double base_asset_balance = market.c_get_balance(market_info.base_currency)
            double quote_asset_balance = market.c_get_balance(market_info.quote_currency)
            double required_quote_asset_balance = 0
            double required_base_asset_balance = 0
            list orders = []
            bint has_active_bid = False
            bint has_active_ask = False

        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
            else:
                has_active_ask = True


        for idx in range(self.number_of_orders):
            current_order_size = self.order_start_size + self.order_step_size * idx
            required_quote_asset_balance += ( float(current_order_size) * float(pricing_proposal.buy_order_prices[idx]) )
            required_base_asset_balance += float(current_order_size)
            if market.name == "binance":
                current_order_size = market.c_quantize_order_amount(market_info.symbol, current_order_size, pricing_proposal.buy_order_prices[idx])
            else:
                current_order_size = market.c_quantize_order_amount(market_info.symbol, current_order_size)

            if current_order_size == 0:
                self.logger().network(f"Order size is less than minimum order size for Price: {pricing_proposal.buy_order_prices[idx]} ",
                                      f"The orders for price of {pricing_proposal.buy_order_prices[idx]} are too small for the market. Check configuration")

            orders.append(current_order_size)

        if quote_asset_balance < required_quote_asset_balance:
            self.logger().network(f"Buy(bid) order is not placed because there is not enough Quote asset. "
                                  f"Quote Asset: {quote_asset_balance}, Required Quote Asset: {required_quote_asset_balance}",
                                  f"Not enough asset to place the required buy(bid) orders. Check balances.")

        if (base_asset_balance < required_base_asset_balance):
            self.logger().network(f"Sell(ask) order is not placed because there is not enough Base asset. "
                                  f"Base Asset: {base_asset_balance}, Required Base Asset: {required_base_asset_balance}",
                                  f"Not enough asset to place the required sell(ask) orders. Check balances.")

        return SizingProposal(
            (orders
             if quote_asset_balance >= required_quote_asset_balance and not has_active_bid
             else [0.0]),
            (orders
             if base_asset_balance >= required_base_asset_balance and not has_active_ask else
             [0.0])
        )