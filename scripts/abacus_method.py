from typing import List

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.model.order import Order
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AbacusMethod(ScriptStrategyBase):
    """
    BotCamp Cohort: Jan 2023
    Design Template: https://hummingbot-foundation.notion.site/Abacus-Method-Strategy-Template-4c8d0f4b1c4b4b7e8a5a5a5a5a5a5a5a
    Video: -
    Description:
    This script relies on GPT to suggest the best strategy for a given market
    """

    # The following strategy dictionary are parameters that the script operator can adjust
    strategy = {
        "market": "binance_paper_trade",
        "pair": "BTC-USDT"
    }

    markets = {strategy["market"]: {strategy["pair"]}}

    @property
    def connector(self) -> ExchangeBase:
        return self.connectors[self.strategy["market"]]

    def on_tick(self):
        """
        Runs every tick_size seconds, this is the main operation of the strategy.
        This method does two things:
        - Refreshes the current bid and ask if they are set to None
        - Cancels the current bid or current ask if they are past their order_refresh_time
          The canceled orders will be refreshed next tic
        """
        ##
        # refresh order logic
        ##
        active_orders = self.get_active_orders(self.strategy["market"])
        # determine if we have an active bid and ask. We will only ever have 1 bid and 1 ask, so this logic would not work in the case of hanging orders
        active_bid = None
        active_ask = None
        for order in active_orders:
            if order.is_buy:
                active_bid = order
            else:
                active_ask = order
        proposal: List[OrderCandidate] = []
        if active_bid is None:
            proposal.append(self.create_order(True))
        if active_ask is None:
            proposal.append(self.create_order(False))
        if (len(proposal) > 0):
            self.execute_proposal(proposal, self.strategy["market"])

    def create_order(self, is_buy: bool) -> OrderCandidate:
        """
        Creates an order candidate that will be submitted to the exchange.
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        amount = self.strategy["amount"]
        price = self.get_price(is_buy)
        return OrderCandidate(is_buy, price, amount, self.strategy["market"], self.strategy["pair"])

    def get_price(self, is_buy: bool) -> float:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        mid_price = self.get_mid_price(self.strategy["market"], self.strategy["pair"])
        if is_buy:
            return mid_price * (1 - self.strategy["bid_spread"])
        else:
            return mid_price * (1 + self.strategy["ask_spread"])

    def get_mid_price(self, market: str, pair: str) -> float:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        return (self.get_price_from_exchange(market, pair, True) + self.get_price_from_exchange(market, pair, False)) / 2

    def get_price_from_exchange(self, market: str, pair: str, is_buy: bool) -> float:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        return self.get_order_book(market, pair).get_price(is_buy)

    def get_active_orders(self, market: str) -> List[Order]:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        return self.get_order_tracker(market).active_orders

    def execute_proposal(self, proposal: List[OrderCandidate], market: str):
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        self.submit_proposal(proposal, market)

    def get_order_book(self, market: str, pair: str) -> OrderBook:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        return self.get_order_tracker(market).order_books[pair]

    def get_order_tracker(self, market: str) -> OrderTracker:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        return self.get_connector(market).order_tracker

    def get_connector(self, market: str) -> ExchangeBase:
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        return self.connectors[market]

    def submit_proposal(self, proposal: List[OrderCandidate], market: str):
        """
        This method is called every tick_size seconds, and will only be called if there is no active bid or ask.
        """
        self.submit_order_candidates(proposal, market)
