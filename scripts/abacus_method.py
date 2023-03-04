from typing import List

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.model.order import Order
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

CHAT_GPT_SCRIPT = """
Your job is to recommend daily strategies for a crypto-bot given current market data.
I will provide the following data (pulled from a centralized exchange) for several Trading Pairs:

|  Data Points               | Description |
|----------------------------|-------------|
|  Historical Price          | Time-series data of the price of the trading pair, with data points including the opening price, closing price, high price, and low price for each trading day.|
|  Real-Time Order Book Data | Data that shows the current buy and sell orders for the asset, including the order quantity and price. |
|  Volume Data               | Data that shows the trading volume of the asset, including the number of trades and the total amount of assets traded over a specified period. |
|  Spread Data               | Data that shows the spread between the bid and ask prices for the asset, including the current spread and historical spread data. |
|  Market Depth Data         | Data that shows the quantity of buy and sell orders at different price levels, including the number of orders and the total order quantity at each price level. |
|  News and Events           | Data that tracks news and events that may impact the market, including economic reports, regulatory changes, and other relevant news items. |

Given the above data, you will need to recommend 2-3 market making strategies for the bot to follow on a paper-trading.
Each market making strategy should include the following data:

|  Data Points               | Description |
|----------------------------|-------------|
| market              | Token trading pair for the exchange, e.g. BTC-USDT |
| bid_spread          | How far away from mid price to place the bid order. Spread of 1 = 1% away from mid price at that time. Example if mid price is 100 and bid_spread is 1. Your bid is placed at 99. |
| ask_spread          | How far away from mid price to place the ask order. Spread of 1 = 1% away from mid price at that time. Example if mid price is 100 and ask_spread is 1. Your bid is placed at 101. |
| minimum_spread| How far away from the mid price to cancel active orders |
| order_refresh_time | Time in seconds before cancelling and placing new orders. If the value is 60, the bot cancels active orders and placing new ones after a minute. |
| max_order_age | Time in seconds before replacing existing order with new orders at the same price.|
| order_refresh_tolerance_pct | The spread (from mid price) to defer order refresh process to the next cycle. (Enter 1 to indicate 1%), value below 0, e.g. -1, is to disable this feature - not recommended. |
| order_amount | Size of your bid and ask order. |
| price_ceiling | Price band ceiling. |
| price_floor | Price band floor. |
| moving_price_band_enabled | enable moving price floor and ceiling. |
| price_ceiling_pct | Price band ceiling pct. |
| price_floor_pct | Price band floor pct. |
| price_band_refresh_time | price_band_refresh_time |
| order_levels | Number of levels of orders to place on each side of the order book. |
| order_level_amount | Increase or decrease size of consecutive orders after the first order (if order_levels > 1). |
| order_level_spread | Order price space between orders (if order_levels > 1). |
| filled_order_delay | How long to wait before placing the next order in case your order gets filled. |
| hanging_orders_enabled | Whether to stop cancellations of orders on the other side (of the order book), when one side is filled (hanging orders feature) (true/false). |
| hanging_orders_cancel_pct | Spread (from mid price, in percentage) hanging orders will be canceled (Enter 1 to indicate 1%) |
"""


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
        return (self.get_price_from_exchange(market, pair, True) + self.get_price_from_exchange(market, pair,
                                                                                                False)) / 2

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
