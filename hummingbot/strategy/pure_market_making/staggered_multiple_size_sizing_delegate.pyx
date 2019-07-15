from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
import logging
from hummingbot.core.event.events import (
OrderType,
TradeType,
TradeFee
)
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
            double base_asset_balance = market.c_get_balance(market_info.base_asset)
            double quote_asset_balance = market.c_get_balance(market_info.quote_asset)
            double required_quote_asset_balance = 0
            double required_base_asset_balance = 0
            list buy_orders = []
            list sell_orders = []
            bint has_active_bid = False
            bint has_active_ask = False

        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
            else:
                has_active_ask = True


        for idx in range(self.number_of_orders):
            current_order_size = self.order_start_size + self.order_step_size * idx
            buy_fees = market.c_get_fee(market_info.base_asset, market_info.quote_asset,
                                    OrderType.MARKET, TradeType.BUY,
                                    current_order_size, pricing_proposal.buy_order_prices[idx])

            if market.name == "binance":
                #For binance fees is calculated in base token, so need to adjust for that
                buy_order_size = market.c_quantize_order_amount(market_info.trading_pair, current_order_size, pricing_proposal.buy_order_prices[idx])
                #Check whether you have enough quote tokens
                required_quote_asset_balance += ( float(buy_order_size) * float(pricing_proposal.buy_order_prices[idx]) )

            else:
                buy_order_size = market.c_quantize_order_amount(market_info.trading_pair, current_order_size)
                #For other exchanges, fees is calculated in quote tokens, so need to ensure you have enough for order + fees
                required_quote_asset_balance += ( float(buy_order_size) * float(pricing_proposal.buy_order_prices[idx]) *(1+float(buy_fees.percent)) )

            sell_order_size = market.c_quantize_order_amount(market_info.trading_pair, current_order_size, pricing_proposal.sell_order_prices[idx])
            required_base_asset_balance += float(sell_order_size)
            if self._log_warning_order_size:
                if buy_order_size == 0 :
                    self.logger().network(f"Buy Order size is less than minimum order size for Price: {pricing_proposal.buy_order_prices[idx]} ",
                                          f"The orders for price of {pricing_proposal.buy_order_prices[idx]} are too small for the market. Check configuration")

                    #After warning once, set warning flag to False
                    self._log_warning_order_size = False

                if sell_order_size == 0 :
                    self.logger().network(f"Sell Order size is less than minimum order size for Price: {pricing_proposal.sell_order_prices[idx]} ",
                                          f"The orders for price of {pricing_proposal.sell_order_prices[idx]} are too small for the market. Check configuration")

                    #After warning once, set warning flag to False
                    self._log_warning_order_size = False

            buy_orders.append(buy_order_size)
            sell_orders.append(sell_order_size)

        if self._log_warning_balance:
            if quote_asset_balance < required_quote_asset_balance:
                self.logger().network(f"Buy(bid) order is not placed because there is not enough Quote asset. "
                                      f"Quote Asset: {quote_asset_balance}, Required Quote Asset: {required_quote_asset_balance}",
                                      f"Not enough asset to place the required buy(bid) orders. Check balances.")
                #After warning once, set warning flag to False
                self._log_warning_balance = False

            if base_asset_balance < required_base_asset_balance:
                self.logger().network(f"Sell(ask) order is not placed because there is not enough Base asset. "
                                      f"Base Asset: {base_asset_balance}, Required Base Asset: {required_base_asset_balance}",
                                      f"Not enough asset to place the required sell(ask) orders. Check balances.")
                #After warning once, set warning flag to False
                self._log_warning_balance = False


        #Reset warnings for balance if there is enough balance to place both orders
        if (quote_asset_balance >= required_quote_asset_balance) and \
                (base_asset_balance >= required_base_asset_balance):
            self._log_warning_balance = True

        #Reset warnings for order size if there are no zero sized orders in buy and sell
        if 0 not in buy_orders and 0 not in sell_orders:
            self._log_warning_order_size = True

        return SizingProposal(
            (buy_orders
             if quote_asset_balance >= required_quote_asset_balance and not has_active_bid
             else [0.0]),
            (sell_orders
             if base_asset_balance >= required_base_asset_balance and not has_active_ask else
             [0.0])
        )