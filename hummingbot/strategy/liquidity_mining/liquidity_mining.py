from decimal import Decimal
import logging
import asyncio
from typing import Dict, List
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from .data_types import Proposal, PriceSize
from hummingbot.core.event.events import OrderType
from hummingbot.core.data_type.limit_order import LimitOrder

NaN = float("nan")
s_decimal_zero = Decimal(0)
lms_logger = None


class LiquidityMiningStrategy(StrategyPyBase):
    """
    This is a basic arbitrage strategy which can be used for most types of connectors (CEX, DEX or AMM).
    For a given order amount, the strategy checks both sides of the trade (market_1 and market_2) for arb opportunity.
    If presents, the strategy submits taker orders to both market.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lms_logger
        if lms_logger is None:
            lms_logger = logging.getLogger(__name__)
        return lms_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 market_infos: Dict[str, MarketTradingPairTuple],
                 initial_spread: Decimal,
                 order_refresh_time: float,
                 order_refresh_tolerance_pct: Decimal,
                 status_report_interval: float = 900):
        super().__init__()
        self._exchange = exchange
        self._market_infos = market_infos
        self._initial_spread = initial_spread
        self._order_refresh_time = order_refresh_time
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._ev_loop = asyncio.get_event_loop()
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._ready_to_trade = False
        self._refresh_times = {market: 0 for market in market_infos}
        self.add_markets([exchange])

    @property
    def active_orders(self):
        limit_orders = self.order_tracker.active_limit_orders
        return [o[1] for o in limit_orders]

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._ready_to_trade:
            self._ready_to_trade = self._exchange.ready
            if not self._exchange.ready:
                self.logger().warning(f"{self._exchange.name} is not ready. Please wait...")
                return
            else:
                self.logger().info(f"{self._exchange.name} is ready. Trading started.")

        proposals = self.create_base_proposals()
        self.apply_volatility_adjustment(proposals)
        self.execute_orders_proposal(proposals)
        self.cancel_active_orders(proposals)
        # if self.c_to_create_orders(proposal):
        #     self.c_execute_orders_proposal(proposal)

        self._last_timestamp = timestamp

    async def format_status(self) -> str:
        return "Not implemented"

    def start(self, clock: Clock, timestamp: float):
        pass

    def stop(self, clock: Clock):
        pass

    def create_base_proposals(self):
        proposals = []
        for market, market_info in self._market_infos.items():
            mid_price = market_info.get_mid_price()
            buy_price = mid_price * (Decimal("1") - self._initial_spread)
            buy_price = self._exchange.quantize_order_price(market, buy_price)
            buy_size = Decimal("0.2")
            buy_size = self._exchange.quantize_order_amount(market, buy_size)

            sell_price = mid_price * (Decimal("1") + self._initial_spread)
            sell_price = self._exchange.quantize_order_price(market, sell_price)
            sell_size = Decimal("0.2")
            sell_size = self._exchange.quantize_order_amount(market, sell_size)
            proposals.append(Proposal(market, PriceSize(buy_price, buy_size), PriceSize(sell_price, sell_size)))
        return proposals

    def apply_volatility_adjustment(self, proposals):
        return

    def is_within_tolerance(self, cur_orders: List[LimitOrder], proposal: Proposal):
        cur_buy = [o for o in cur_orders if o.is_buy]
        cur_sell = [o for o in cur_orders if not o.is_buy]
        if (cur_buy and proposal.buy.size == 0) or (cur_sell and proposal.sell.size == 0):
            return False
        if abs(proposal.buy.price - cur_buy[0].price) / cur_buy[0].price > self._order_refresh_tolerance_pct:
            return False
        if abs(proposal.sell.price - cur_sell[0].price) / cur_sell[0].price > self._order_refresh_tolerance_pct:
            return False
        return True

    def cancel_active_orders(self, proposals):
        for proposal in proposals:
            if self._refresh_times[proposal.market] > self.current_timestamp:
                continue
            cur_orders = [o for o in self.active_orders if o.trading_pair == proposal.market]
            if not cur_orders or self.is_within_tolerance(cur_orders, proposal):
                continue
            for order in cur_orders:
                self.cancel_order(self._market_infos[proposal.market], order.client_order_id)

    def execute_orders_proposal(self, proposals):
        for proposal in proposals:
            cur_orders = [o for o in self.active_orders if o.trading_pair == proposal.market]
            if cur_orders:
                continue
            if proposal.buy.size > 0:
                self.logger().info(f"({proposal.market}) Creating a bid order {proposal.buy}")
                self.buy_with_specific_market(
                    self._market_infos[proposal.market],
                    proposal.buy.size,
                    order_type=OrderType.LIMIT_MAKER,
                    price=proposal.buy.price
                )
            if proposal.sell.size > 0:
                self.logger().info(f"({proposal.market}) Creating an ask order at {proposal.sell}")
                self.sell_with_specific_market(
                    self._market_infos[proposal.market],
                    proposal.sell.size,
                    order_type=OrderType.LIMIT_MAKER,
                    price=proposal.sell.price
                )
            if proposal.buy.size > 0 or proposal.sell.size > 0:
                self._refresh_times[proposal.market] = self.current_timestamp + self._order_refresh_time
