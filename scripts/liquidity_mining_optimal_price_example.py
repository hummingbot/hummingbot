import logging
import requests

from typing import List
from decimal import Decimal
from typing import List

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent

class Order():
    def __init__(self, order_id, trade_type: TradeType, price, datetime_placed):
        self.order_id = order_id
        self.trade_type = trade_type
        self.price = price
        self.datetime_placed = datetime_placed

class HistoricalTradeDataFetcher():

    WAIT_TIME = 5 # wait time before fetching data again
    TRADES_TO_FETCH = 1000

    last_fetched_timestamp = 0
    max_trade_volume = 0

    def get_max_trade_volume(self, trading_pair, current_timestamp):
        """ 
            Fetch historical market trade data and find the max trade volume
        """
        # check if desired amount of time has pased before fetching historical data again
        # this prevents sending requests to Binancec API too frequently 
        if self.last_fetched_timestamp + self.WAIT_TIME < current_timestamp:
            trades = self.fetch_historical_trades(trading_pair, self.TRADES_TO_FETCH)
            self.max_trade_volume = 0

            for trade in trades:
                trade_qty = float(trade["qty"])
                if trade_qty > self.max_trade_volume:
                    self.max_trade_volume = trade_qty

            self.last_fetched_timestamp = current_timestamp

        return self.max_trade_volume 

    def fetch_historical_trades(self, trading_pair: str, limit) -> List[Decimal]:
        """
        Fetches historical market trade data

        This is the API response data structure:
        [
            {
                "id": 28457,
                "price": "4.00000100",
                "qty": "12.00000000",
                "quoteQty": "48.000012",
                "time": 1499865549590,
                "isBuyerMaker": true,
                "isBestMatch": true
            },
        ]

        :param trading_pair: A market trading pair to
        :param limit: Trades to fetch, 1000 max
        :return: A list of daily close
        """

        url = "https://api.binance.com/api/v3/trades"
        params = {
            "symbol": trading_pair.replace("-", ""),
            "limit": f"{limit}"
        }

        trades = requests.get(url = url, params = params).json()
        return trades

class SimplePMM(ScriptStrategyBase):

    EXCHANGE = 'binance'
    TRADING_PAIR = 'FRONT-BUSD'
    MAX_ORDER_AGE = 30 # 30 seconds
    ORDER_AMOUNT_FRONT = 80

    buy_order: Order = None
    sell_order: Order = None

    historical_trade_data_fetcher = HistoricalTradeDataFetcher()

    markets = { EXCHANGE: { TRADING_PAIR } }

    def on_tick(self):

        # get gistorical max trade volume
        max_trade_volume = self.historical_trade_data_fetcher.get_max_trade_volume(self.TRADING_PAIR, self.current_timestamp)
        
        # get bid and ask entries
        order_book = self.connectors[self.EXCHANGE].get_order_book(self.TRADING_PAIR)
        bid_entries = order_book.bid_entries()
        ask_entries = order_book.ask_entries()

        # get optimal prices based on volume
        buy_price = self.get_optimal_price(bid_entries, max_trade_volume)
        sell_price = self.get_optimal_price(ask_entries, max_trade_volume)


        # Handle buy order
        if not self.buy_order: 
            buy_proposal = self.create_buy_proposal(buy_price)
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(self.EXCHANGE, [buy_proposal])
            buy_order_id = self.place_order(connector_name = self.EXCHANGE, order = proposal_adjusted[0])

            self.buy_order = Order(buy_order_id, TradeType.BUY, buy_price, self.current_timestamp)
        else:
            if (
                # cancel if - order is reached its max age
                (self.is_order_max_age_reached(self.buy_order) and self.has_price_changed(self.buy_order, buy_price))
                # or order price is the first price in the order book
                or self.is_order_price_first_in_order_book(self.buy_order, bid_entries)
            ):
                self.cancel(self.EXCHANGE, self.TRADING_PAIR, self.buy_order.order_id)
                self.buy_order = None

        # Handle sell order
        if not self.sell_order:
            sell_proposal = self.create_sell_proposal(sell_price)
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(self.EXCHANGE, [sell_proposal])
            sell_order_id = self.place_order(connector_name = self.EXCHANGE, order = proposal_adjusted[0])

            self.sell_order = Order(sell_order_id, TradeType.BUY, sell_price, self.current_timestamp)
        else:
            if (
                # cancel if - order is reached its max age
                (self.is_order_max_age_reached(self.sell_order) and self.has_price_changed(self.sell_order, sell_price))
                # or order price is the first price in the order book
                or self.is_order_price_first_in_order_book(self.sell_order, ask_entries)
            ):
                self.cancel(self.EXCHANGE, self.TRADING_PAIR, self.sell_order.order_id)
                self.sell_order = None

    def get_optimal_price(self, entries, min_volume):
        """ 
            Purpose of the method is to get the price from the order book which sits after the certain volume
            
            Logic:
            Goes through bid/ask entries
            Sums the volume of each entry on each iteration (collected_volume)
            As soon as collected_volume is >= than min_volume the loop will be stopped and optimal price will be returned
        """
        collected_volume = 0
        optimal_price = 0

        for entry in entries:
            if collected_volume >= min_volume:
                optimal_price = entry.price
                break
            collected_volume += entry.amount

        return optimal_price

    def is_order_max_age_reached(self, order: Order):
        return order.datetime_placed + self.MAX_ORDER_AGE < self.current_timestamp

    def has_price_changed(self, order: Order, price):
        rounded_order_price = round(float(order.price), 4)
        rounded_price = round(float(price), 4)
        return rounded_order_price != rounded_price

    def is_order_price_first_in_order_book(self, order: Order, order_book_entries):
        first_order_book_price = round(float(next(order_book_entries).price), 4)
        order_price = round(float(order.price), 4)
        return first_order_book_price == order_price

    def create_buy_proposal(self, buy_price):
        return OrderCandidate(
            trading_pair = self.TRADING_PAIR,
            is_maker = True, 
            order_type = OrderType.LIMIT, 
            order_side = TradeType.BUY,
            amount = Decimal(self.ORDER_AMOUNT_FRONT), 
            price = Decimal(buy_price)
        )

    def create_sell_proposal(self, sell_price):
        return OrderCandidate(
            trading_pair = self.TRADING_PAIR,
            is_maker = True, 
            order_type = OrderType.LIMIT, 
            order_side = TradeType.SELL,
            amount = Decimal(self.ORDER_AMOUNT_FRONT),
            price = Decimal(sell_price)
        )
    
    def adjust_proposal_to_budget(self, exchange, proposal: List[OrderCandidate]):
        proposal_adjusted = self.connectors[exchange].budget_checker.adjust_candidates(proposal, all_or_none = True)
        return proposal_adjusted

    def place_order(self, connector_name: str, order: OrderCandidate):
        order_id = None
        if order.order_side == TradeType.SELL:
            order_id = self.sell(
                connector_name = connector_name, 
                trading_pair = order.trading_pair,
                amount = order.amount,
                order_type = order.order_type,
                price = order.price
            )
        elif order.order_side == TradeType.BUY:
            order_id = self.buy(
                connector_name = connector_name, 
                trading_pair = order.trading_pair,
                amount = order.amount,
                order_type = order.order_type,
                price = order.price
            )

        return order_id
    
    def did_fill_order(self, event: OrderFilledEvent):
        msg = f'Filled {event.trade_type} {event.amount} {event.trading_pair} at {round(event.price, 4)}'
        self.log_and_send_message(msg)

    def log_message(self, msg):
        self.log_with_clock(logging.INFO, msg)
    
    def log_and_send_message(self, msg):
        self.log_message(msg)
        self.notify_hb_app_with_timestamp(msg)

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        lines.extend(["", "  Historical Max Trade Volume:"] + ["    " + str(self.historical_trade_data_fetcher.max_trade_volume)])

        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
        