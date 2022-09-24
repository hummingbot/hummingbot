import logging
import time
from decimal import Decimal
from statistics import mean
from typing import List

import numpy as np
import pandas as pd

import requests

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType  # Just need PriceType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.__utils__.trailing_indicators.price_range_indicator import PriceRangeIndicator

class SpreadAdjustedOnPriceRange(ScriptStrategyBase):
    """
    This script calculates the high and low prices from the last x seconds and
    uses that to set the spread amount for the bid and ask orders.
    """
    connector_name: str = "binance_paper_trade"
    trading_pair: str = "ETH-USDT"
    base_asset, quote_asset = split_hb_trading_pair(trading_pair)
    order_amount = Decimal("0.1") # ETH
    price_range_period: int = 300 # How many seconds to use as the window for the price range indicator
    bid_spread = Decimal("1") # Spread from the current price in percentage (1 = 1%)
    ask_spread = Decimal("1") # Spread from the current price in percentage (1 = 1%)
    #: A cool off period before the next order is created (in seconds)
    cool_off_interval: float = 10.
    #: The last filled timestamp
    last_buy_ts: float = 1.
    last_sell_ts: float = 1.
    adjusted_bid_spread = Decimal("0")
    adjusted_ask_spread = Decimal("0")

    markets = {connector_name: {trading_pair}}
    price_range_indicator = PriceRangeIndicator(sampling_length=price_range_period)

    @property
    def connector(self) -> ExchangeBase:
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.connector_name]

    def on_tick(self):
        """
        Runs every tick_size seconds, this is the main operation of the strategy.
        - Log the current price into the PriceRangeIndicator
        - Verify we have no outstanding active orders, otherwise we wait until the next tick
          (in production we would want to cancel orders that have not been filled within a certain
          amount of time if the price has drifted more than a certain amount)
        - Create proposal (a list of order candidates) using the spread as the range between
          the high and low prices for the last x seconds from the indicator
        - Check the account balance and adjust the proposal accordingly (lower order amount if needed)
        - Lastly, execute the proposal on the exchange
        """
        last_price = self.connector.get_price_by_type(self.trading_pair, PriceType.LastTrade)
        self.price_range_indicator.add_sample(last_price)
        if self.price_range_indicator.buffer_size < min(10, self.price_range_period):
            return
        if not self.get_active_orders(self.connector_name):
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal = self.connector.budget_checker.adjust_candidates(proposal, all_or_none=False)
            if proposal:
                self.execute_proposal(proposal)
        else:
            self.log_with_clock(logging.INFO, f"Waiting for orders to fill: {self.get_active_orders(self.connector_name)}")

    def create_proposal(self) -> List[OrderCandidate]:
        """
        Creates and returns a proposal (a list of order candidate), in this strategy the list has 2 elements at most.
        """
        rolling_spread = Decimal(str(self.price_range_indicator.current_value))
        price = self.connector.get_mid_price(self.trading_pair)
        bid_spread_amount = (self.bid_spread / Decimal('100')) * price
        ask_spread_amount = (self.ask_spread / Decimal('100')) * price
        if rolling_spread:
            bid_spread_amount = rolling_spread / Decimal("2")
            ask_spread_amount = bid_spread_amount

        self.adjusted_bid_spread = (bid_spread_amount / price) * Decimal('100')
        self.adjusted_ask_spread = (ask_spread_amount / price) * Decimal('100')
        bid_price = price - bid_spread_amount
        ask_price = price + ask_spread_amount

        self.log_with_clock(logging.INFO, f"Creating proposal with bid_spread {self.adjusted_bid_spread:.4f}% and ask_spread {self.adjusted_ask_spread:.4f}%")
        proposal = []
        proposal.append(OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=self.order_amount,
            price=bid_price
        ))
        proposal.append(OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=self.order_amount,
            price=ask_price
        ))

        return proposal

    def execute_proposal(self, proposal: List[OrderCandidate]):
        """
        Places the order candidates on the exchange, if it is not within cool off period and order candidate is valid.
        """
        if self.last_buy_ts == 0 or self.last_sell_ts == 0:
            self.log_with_clock(logging.INFO, f"Ignoring proposal until active orders are filled")
            return
        if (self.last_buy_ts > time.time() - self.cool_off_interval
            or self.last_sell_ts > time.time() - self.cool_off_interval
            ):
            self.log_with_clock(logging.INFO, f"Ignoring proposal until cool off interval has elapsed")
            return
        for order_candidate in proposal:
            if order_candidate.amount > Decimal("0"):
                if order_candidate.order_side == TradeType.BUY:
                    self.buy(self.connector_name, self.trading_pair, order_candidate.amount, order_candidate.order_type,
                             order_candidate.price)
                    self.last_buy_ts = 0
                else:
                    self.sell(self.connector_name, self.trading_pair, order_candidate.amount, order_candidate.order_type,
                              order_candidate.price)
                    self.last_sell_ts = 0

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Listens to fill order event to log it and notify the hummingbot application.
        If you set up Telegram bot, you will get notification there as well.
        """
        if event.trade_type.name == "BUY":
            self.last_buy_ts = time.time()
        elif event.trade_type.name == "SELL":
            self.last_sell_ts = time.time()
        msg = (f"({event.trading_pair}) {event.trade_type.name} order (price: {event.price}) of {event.amount} "
               f"{split_hb_trading_pair(event.trading_pair)[0]} is filled.")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def spread_df(self) -> pd.DataFrame:
        """
        Return a data frame of the calculated spread values to use when making orders.
        """
        price = self.connector.get_mid_price(self.trading_pair)
        columns = ["Window", "Price", "Low", "High", "Spread", "Bid", "Ask"]
        data = []
        data.append([
            self.price_range_indicator.buffer_size,
            f"{price:.4f}",
            f"{self.price_range_indicator.low:.4f}",
            f"{self.price_range_indicator.high:.4f}",
            f"{(Decimal(str(self.price_range_indicator.current_value)) / price):.3%}",
            f"{self.adjusted_bid_spread:.3f}%",
            f"{self.adjusted_ask_spread:.3f}%",
        ])
        df = pd.DataFrame(data=data, columns=columns)
        return df

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        spread_df = self.spread_df()
        lines.extend(["", "  Calculated Spread:"] + ["    " + line for line in spread_df.to_string(index=False).split("\n")])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
