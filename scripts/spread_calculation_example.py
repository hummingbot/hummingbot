import logging
import collections
import statistics
import math 

import pandas as pd

from typing import List
from decimal import Decimal
from typing import Dict, List

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.data_type.composite_order_book import CompositeOrderBook

class VolumeAnalyzer():

    def __init__(self, connector, pair):
        self.connector = connector
        self.pair = pair
        self.buy_amounts = collections.deque([])
        self.sell_amounts = collections.deque([])
        self.previous_timestamp = None
        self.buy_mean_amount = None
        self.sell_mean_amount = None
        self.buy_standard_deviation = None 
        self.sell_standard_deviation = None 
        self.buy_mean_and_stdev_sum = None
        self.sell_mean_and_stdev__sum = None
        self.mid_price = None
        self.buy_spread = None
        self.sell_spread = None

    def add_buy_amount(self, buy_amount):
        self.buy_amounts.append(buy_amount)

    def add_sell_amount(self, sell_amount):
        self.sell_amounts.append(sell_amount)

    def get_previous_timestamp(self):
        return self.previous_timestamp

    def set_previous_timestamp(self, previous_timestamp):
        self.previous_timestamp = previous_timestamp

    def calculate_mean_and_stdev(self):
        if len(self.buy_amounts) > 0:
            self.buy_mean_amount = statistics.mean(self.buy_amounts)
            buy_variance = statistics.variance(self.buy_amounts, self.buy_mean_amount)
            self.buy_standard_deviation = math.sqrt(buy_variance)
            self.buy_mean_and_stdev_sum = self.buy_mean_amount + self.buy_standard_deviation

        if len(self.sell_amounts) > 0:
            self.sell_mean_amount = statistics.mean(self.sell_amounts)
            sell_variance = statistics.variance(self.sell_amounts, self.sell_mean_amount)
            self.sell_standard_deviation = math.sqrt(sell_variance)
            self.sell_mean_and_stdev__sum = self.sell_mean_amount + self.sell_standard_deviation
    
    def clear_amounts(self):
        self.buy_amounts.clear()
        self.sell_amounts.clear()

    def calculate_spreads(self):
        self.mid_price = self.connector.get_mid_price(self.pair) 

        buy_for_volume_result = self.connector.get_price_for_volume(self.pair, True, self.buy_mean_and_stdev_sum)
        self.buy_spread = self.__percentage_diff(buy_for_volume_result.result_price, self.mid_price)
        self.buy_spread = round(self.buy_spread, 2) 

        sell_for_volume_result = self.connector.get_price_for_volume(self.pair, False, self.sell_mean_and_stdev__sum)
        self.sell_spread = self.__percentage_diff(sell_for_volume_result.result_price, self.mid_price)
        self.sell_spread = round(self.sell_spread, 2)

    def __percentage_diff(self, value1, value2):
        return (abs(value1 - value2) / ((value1 + value2) / 2)) * 100

class SpreadCalculator():
    
    volume_analyzer: VolumeAnalyzer = None

    def __init__(self, data_collection_interval, connector, pair):
        self.volume_analyzer = VolumeAnalyzer(connector, pair)
        self.data_collection_interval = data_collection_interval

    def calculate_mean_and_stdev(self, timestamp):
        if not self.volume_analyzer.get_previous_timestamp():
            self.volume_analyzer.set_previous_timestamp(timestamp)

        if timestamp - self.volume_analyzer.get_previous_timestamp() > self.data_collection_interval:
            self.volume_analyzer.set_previous_timestamp(timestamp)
            self.volume_analyzer.calculate_mean_and_stdev()
            self.volume_analyzer.clear_amounts()
            self.volume_analyzer.calculate_spreads()

    def add_buy_amount(self, amount):
        self.volume_analyzer.add_buy_amount(amount)

    def add_sell_amount(self, amount):
        self.volume_analyzer.add_sell_amount(amount)

    def get_buy_spread(self):
        return self.volume_analyzer.buy_spread

    def get_sell_spread(self):
        return self.volume_analyzer.sell_spread

    def get_data_df(self):
        columns = ["Exchange", "Pair", "BuyOrders", "SellOrders", "MidPrice", "MeanBuy", "MeanSell", "BuyStDev", "SellStDev", "BuyMean+StdDev", "SellMean+StdDev", "BuySpread", "SellSpread"]
        data = []

        data.append([
            # Exchange 
            self.volume_analyzer.connector.name,
            # Pair 
            self.volume_analyzer.pair,
            # Buy Orders 
            len(self.volume_analyzer.buy_amounts),
            # Sell Orders 
            len(self.volume_analyzer.sell_amounts),
            # Mid Price 
            self.volume_analyzer.mid_price,
            # Buy Mean Amount 
            self.volume_analyzer.buy_mean_amount,
            # Sell Mean Amount 
            self.volume_analyzer.sell_mean_amount,
            # Buy Standard Deviation
            self.volume_analyzer.buy_standard_deviation,
            # Sell Standard Deviation
            self.volume_analyzer.sell_standard_deviation,
            # Sum of Buy Mean and Standard Deviation 
            self.volume_analyzer.buy_mean_and_stdev_sum,
            # Sum of Sell Mean and Standard Deviation
            self.volume_analyzer.sell_mean_and_stdev__sum,
            # Buy Spread 
            self.volume_analyzer.buy_spread,
            # Sell Spread 
            self.volume_analyzer.sell_spread
        ])

        df = pd.DataFrame(data=data, columns=columns)
        return df

class SimplePMM(ScriptStrategyBase):

    EXCHANGE = 'binance_paper_trade'
    TRADING_PAIR = 'BNB-USDT'
    DATA_COLLECTION_INTERVAL = 60 * 60
    INCREASE_SPREAD_BY_PCT = 0.1

    ORDER_REFRESH_TIME = 65
    ORDER_AMOUNT_USDT = 150
    PRICE_SOURCE = PriceType.MidPrice

    create_timestamp = 0 
    order_book_event_initialized = False
    spread_calculator: SpreadCalculator = None

    markets = { EXCHANGE: { TRADING_PAIR } }

    def on_tick(self):

        if not self.spread_calculator:
            self.init_spread_calculator()

        if not self.order_book_event_initialized:
            self.init_order_book_trades_events()

        # Check if it's the time to place orders
        if self.create_timestamp <= self.current_timestamp: 

            for exchange, pairs in self.markets.items():

                # Cancel all orders 
                self.cancel_all_orders(exchange)
                
                for pair in list(pairs):
                    # Create the proposal
                    proposal: List[OrderCandidate] = self.create_proposal(exchange, pair)
                    proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(exchange, proposal)
                    self.place_orders(exchange, proposal_adjusted)

            self.create_timestamp = self.ORDER_REFRESH_TIME + self.current_timestamp

    def init_spread_calculator(self):
        self.spread_calculator = SpreadCalculator(self.DATA_COLLECTION_INTERVAL, self.connectors[self.EXCHANGE], self.TRADING_PAIR)

    def init_order_book_trades_events(self):
        self.order_book_trade_event = SourceInfoEventForwarder(self.process_public_trade)
        for market in self.connectors.values():
            for order_book in market.order_books.values():
                order_book.add_listener(OrderBookEvent.TradeEvent, self.order_book_trade_event)
        self.order_book_event_initialized = True

    def process_public_trade(self, event_tag: int, order_book: CompositeOrderBook, event: OrderBookTradeEvent):
        if event.type == TradeType.BUY:
            self.spread_calculator.add_buy_amount(event.amount)
        elif event.type == TradeType.SELL:
            self.spread_calculator.add_sell_amount(event.amount)

        self.spread_calculator.calculate_mean_and_stdev(event.timestamp)
    
    def cancel_all_orders(self, exchange):
        orders = self.get_active_orders(exchange)
        for order in orders:
            self.cancel(exchange, order.trading_pair, order.client_order_id)

    def create_proposal(self, exchange, trading_pair):

        orders = []

        buy_spread = self.get_buy_spread()
        sell_spread = self.get_sell_spread()

        if buy_spread and sell_spread and buy_spread > 0 and sell_spread > 0:
            self.log_and_send_message(f'Buy spread {buy_spread}% for {trading_pair} on {exchange} will be used')
            self.log_and_send_message(f'Sell spread {sell_spread}% for {trading_pair} on {exchange} will be used')

            # get mid price, calc buy and sell prices
            ref_price = self.connectors[exchange].get_price_by_type(trading_pair, self.PRICE_SOURCE)
            buy_price = ref_price - (ref_price * Decimal(buy_spread / 100))
            sell_price = ref_price + (ref_price * Decimal(sell_spread / 100))

            # prepare buy order candidate
            buy_amount = Decimal(self.ORDER_AMOUNT_USDT) / buy_price # convert the usdt amount to base currency
            buy_order = OrderCandidate(
                trading_pair = trading_pair, 
                is_maker = True, 
                order_type = OrderType.LIMIT, 
                order_side = TradeType.BUY,
                amount = Decimal(buy_amount), 
                price = buy_price
            )
            orders.append(buy_order)

            # prepare sell order candidate
            sell_amount = Decimal(self.ORDER_AMOUNT_USDT)
            sell_order = OrderCandidate(
                trading_pair = trading_pair, 
                is_maker = True, 
                order_type = OrderType.LIMIT, 
                order_side = TradeType.SELL,
                amount = Decimal(sell_amount),
                price = sell_price
            )
            orders.append(sell_order)
        
        else:
            self.log_and_send_message(f'Spreads for {trading_pair} on {exchange} have not yet been calculated')

        return orders

    def get_buy_spread(self):
        buy_spread = self.spread_calculator.get_buy_spread()

        if buy_spread:
            buy_spread = round(buy_spread + (buy_spread * Decimal(self.INCREASE_SPREAD_BY_PCT)), 3)

        return buy_spread

    def get_sell_spread(self):
        sell_spread = self.spread_calculator.get_sell_spread()

        if sell_spread:
            sell_spread = round(sell_spread + (sell_spread * Decimal(self.INCREASE_SPREAD_BY_PCT)), 3)

        return sell_spread

    def adjust_proposal_to_budget(self, exchange, proposal: List[OrderCandidate]):
        proposal_adjusted = self.connectors[exchange].budget_checker.adjust_candidates(proposal, all_or_none = True)
        return proposal_adjusted

    def place_orders(self, exchange, proposal: List[OrderCandidate]):
        for order in proposal:
            self.place_order(connector_name = exchange, order = order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name = connector_name, 
                trading_pair = order.trading_pair,
                amount = order.amount,
                order_type = order.order_type,
                price = order.price
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name = connector_name, 
                trading_pair = order.trading_pair,
                amount = order.amount,
                order_type = order.order_type,
                price = order.price
            )
    
    def log_and_send_message(self, msg):
        self.log_with_clock(logging.INFO, msg)
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

        spread_data_df = self.spread_calculator.get_data_df()
        lines.extend(["", "  Spread Data:"] + ["    " + line for line in spread_data_df.to_string(index=False).split("\n")])

        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
        