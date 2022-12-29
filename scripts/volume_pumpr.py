import logging
from decimal import Decimal
from math import ceil, floor
from typing import List

import pandas as pd

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class VolumePumpr(ScriptStrategyBase):
    # Settings / Inputs
    exchange: str = "binance"
    trading_pair: str = "BTC-BUSD"
    order_amount = Decimal("0.013")  # cca. 200 USD
    price_source = PriceType.MidPrice
    bid_spread_ticks = Decimal("1")
    ask_spread_ticks = Decimal("1")
    jump_closer_deviation_bps = Decimal("0.6")
    force_hedge_slippage_tolerance_bps = 100
    maker_fee_pct = Decimal("0")

    # Do not edit beyond this point
    markets = {exchange: {trading_pair}}
    base: str = ""
    quote: str = ""
    status: str = "NOT_INITIALIZED"
    tick_size = Decimal("0.01")     # Should be updated after initialization

    @property
    def connector(self):
        return self.connectors[self.exchange]

    def on_tick(self):
        if self.status == "NOT_INITIALIZED":
            self.init_strategy()

        if self.any_open_orders():
            self.check_deviation()
        else:
            self.create_order_pair()

    def init_strategy(self):
        """
        Initialize strategy
        - Query and set tick price (price quantum)
        - Query and set taker & maker fees for specific trading pair (just fetches
          it now, because it looks like HB just reads it from defaults instead of querying the exchange)
        """
        self.logger().info("Initializing strategy...")
        best_bid_price = self.connector.get_price(self.trading_pair, False)
        self.tick_size = self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)
        self.logger().info(f"Tick size for {self.trading_pair} on {self.exchange}: {self.tick_size}")
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        maker_fee = build_trade_fee(self.exchange, True, self.base, self.quote, self.connector.get_maker_order_type(), TradeType.BUY, self.order_amount)
        taker_fee = build_trade_fee(self.exchange, True, self.base, self.quote, self.connector.get_taker_order_type(), TradeType.BUY, self.order_amount)
        self.logger().info(f"Maker fee according to HB: {maker_fee}")
        self.logger().info(f"Taker fee according to HB: {taker_fee}")
        self.status = "RUNNING"

    def any_open_orders(self):
        if len(self.get_active_orders(self.exchange)) > 0:
            return True
        else:
            return False

    def is_hanging_order(self):
        return len(self.get_active_orders(self.exchange)) == 1

    #
    # CREATE ORDER PAIRS
    #
    def create_order_pair(self):
        # proposal: List[OrderCandidate] = self.create_proposal()
        bid_proposal: OrderCandidate = self.create_proposal_bid()
        ask_proposal: OrderCandidate = self.create_proposal_ask()

        proposal: List[OrderCandidate] = self.adjust_proposal_pair(bid_proposal, ask_proposal)

        proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
        for p in proposal_adjusted:
            msg = f"Side: {p.order_side}, amount: {p.amount}, price: {p.price}, percent_fee_value: {p.percent_fee_value}"
            self.log_with_clock(logging.INFO, msg)
        self.place_orders(proposal_adjusted)

    def create_proposal_ask(self, order_amount = None, force_market_order = False) -> OrderCandidate:
        if order_amount is None:
            order_amount = self.order_amount
        if force_market_order is False:
            best_ask_price = self.connector.get_price(self.trading_pair, True)
            ask_price = (ceil(best_ask_price / self.tick_size) + self.ask_spread_ticks) * self.tick_size
            ask_price = self.connector.quantize_order_price(self.trading_pair, ask_price / Decimal(1 - self.maker_fee_pct / 100))
        else:
            best_bid_price = self.connector.get_price(self.trading_pair, False)
            ask_price = self.connector.quantize_order_price(self.trading_pair, best_bid_price * Decimal(1 - self.force_hedge_slippage_tolerance_bps / 100000))
        sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.order_amount), price=ask_price)

        return sell_order

    def create_proposal_bid(self, order_amount = None, force_market_order = False) -> OrderCandidate:
        if order_amount is None:
            order_amount = self.order_amount
        if force_market_order is False:
            best_bid_price = self.connector.get_price(self.trading_pair, False)
            bid_price = (floor(best_bid_price / self.tick_size) - self.bid_spread_ticks) * self.tick_size
            bid_price = self.connector.quantize_order_price(self.trading_pair, bid_price / Decimal(1 + self.maker_fee_pct / 100))
        else:
            best_ask_price = self.connector.get_price(self.trading_pair, True)
            bid_price = self.connector.quantize_order_price(self.trading_pair, best_ask_price * Decimal(1 + self.force_hedge_slippage_tolerance_bps / 100000))
        buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(order_amount), price=bid_price)
        return buy_order

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connector.budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def adjust_proposal_pair(self, bid_proposal, ask_proposal) -> List[OrderCandidate]:
        """
        Don't let bid & ask be equal when creating a new order pair to prevent self trading
        """
        best_bid_price = self.connector.get_price(self.trading_pair, False)
        if bid_proposal.price == ask_proposal.price:
            ask_proposal.price = (ceil(bid_proposal.price / self.tick_size) + 1) * self.tick_size
        return [bid_proposal, ask_proposal]

    def place_orders(self, proposal: List[OrderCandidate]):
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        if order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
    #
    # DEVIATION CHECKS
    #

    def check_deviation(self):
        """
        If any order has deviated more than jump_closer_deviation_bps from price, cancel it
        and create a new maker order closer to mid
        """
        if self.status != "RUNNING":
            return
        mid_price = self.connector.get_price_by_type(self.trading_pair, self.price_source)
        for order in self.get_active_orders(self.exchange):
            spread_bps = round(abs(order.price - mid_price) / mid_price * 10000, 1)
            if spread_bps >= self.jump_closer_deviation_bps:
                self.logger().info(f"Order {order.client_order_id} has deviated from mid, placing order closer")
                quantity_remaining = order.quantity
                if not order.filled_quantity.is_nan():
                    quantity_remaining = order.quantity - order.filled_quantity
                if order.is_buy:
                    proposal = self.create_proposal_bid(quantity_remaining)
                else:
                    proposal = self.create_proposal_ask(quantity_remaining)
                adjusted_proposal = self.connector.budget_checker.adjust_candidate(proposal, all_or_none=False)
                self.cancel(self.exchange, self.trading_pair, order.client_order_id)
                self.place_order(self.exchange, adjusted_proposal)
        return

    #
    # EVENTS
    #

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 4)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def stop(self, clock: Clock):
        """
        When stopped, strategy should exit cleanly by force hedging outstanding orders
        """
        self.status = "STOPPING"
        # We just return for now, as this doesn't work as expected
        # c_stop gets called first, which disables trading
        # TODO: fix this
        return
        self.logger().info("Received stop, force hedging remaining orders")
        for order in self.get_active_orders(self.exchange):
            self.logger().info(f"Force hedging order {order.client_order_id}")
            self.force_hedge_order(order)
        return

    def force_hedge_order(self, order: LimitOrder):
        """
        Takes a LimitOrder, cancels it, and places it again as market order
        """
        quantity_remaining = order.quantity
        if not order.filled_quantity.is_nan():
            quantity_remaining = order.quantity - order.filled_quantity
        if order.is_buy:
            proposal = self.create_proposal_bid(quantity_remaining, True)
        else:
            proposal = self.create_proposal_ask(quantity_remaining, True)
        adjusted_proposal = self.connector.budget_checker.adjust_candidate(proposal, all_or_none=False)
        self.cancel(self.exchange, self.trading_pair, order.client_order_id)
        self.place_order(self.exchange, adjusted_proposal)

    #
    # STATUS
    #

    def active_orders_df(self) -> pd.DataFrame:
        """
        Return a data frame of all active orders for displaying purpose.
        """
        columns = ["Side", "Price", "Δticks", "Δbps", "Rem. Amount", "Age"]
        data = []

        mid_price = self.connector.get_mid_price(self.trading_pair)

        for order in self.get_active_orders(self.exchange):
            age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
            dticks = round(abs(order.price - mid_price) / self.tick_size)
            spread_bps = round(abs(order.price - mid_price) / mid_price * 10000, 1)
            quantity_remaining = order.quantity
            if not order.filled_quantity.is_nan():
                quantity_remaining = order.quantity - order.filled_quantity
            data.append([
                "buy" if order.is_buy else "sell",
                float(order.price),
                dticks,
                spread_bps,
                quantity_remaining,
                age_txt
            ])
        if not data:
            raise ValueError
        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Price"], inplace=True)
        return df

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. 
        - Show history
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        # balance_df = self.get_balance_df()
        # lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        lines.extend(["", f"Trading pair: {self.trading_pair}"])
        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
