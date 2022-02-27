# distutils: language=c++
# The Triangular Arbitrage Strategy is used to trade between three linked currency pairs on a single exchange. The strategy starts and ends with the same currency holdings and 
# seeks to profit through the difference of exchange rates amongst the three pairs traded. For example using the three pairs FRONT/BTC, BTC/USDT and FRONT/USDT if you started with 1000 FRONT
# this could be exchanged for BTC which could then be exchanged for USDT and then back to FRONT. If the price of FRONT to BTC in dollar terms were offset from the price to USDT this could result
# in a profit. The major hurdle here is that three trades also attract three lots of exchange fees which would greatly reduce the profitability so these must be taken into consideration within the calculation
# and the offset in value beween various pairs muct be quite extreme to profit.

# The strategy always involves three separate currencies and it allows for a starting balance in any one of these currencies or multiple. The strategy tests the resulting profitability from any of the 
# six possible combinations of trades (starting from any of the three pairs and either going clockwise or anticlockwise around the process). Taking into account available balance the most profitable option is found
# The order amount is then optimised from the vwap using the order book and if resulting profitability is above min proftability trading mode is activated. this is done in a progressive order in which the second trade is not started until the first trade has completed
# to ensure enough balance is available. this is completed over several ticks. when the third trade is completed the system is reset and starts to monitor profitability again.
# IMPORTANT THE TRIANGULAR ARBITRAGE STARTEGY RELIES ON MARKET ORDERS RATHER THAN LIMIT ORDERS SO WILL NOT BENEFIT THOSE LOOKING TO PROFIT FROM HUMMINGBOT MINER.

import logging
import random
import time
from decimal import Decimal
import pandas as pd
from csv import reader
from typing import (
    List,
    Tuple,
)

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import (
    TradeType,
    OrderType,
)
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.tri_arbitrage.tri_arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.strategy.tri_arbitrage.tri_arbitrage import ArbitrageStrategy
from hummingbot.strategy.tri_arbitrage.tri_arbitrage_config_map import tri_arbitrage_config_map

NaN = float("nan")
s_decimal_0 = Decimal(0)
as_logger = None


cdef class ArbitrageStrategy(StrategyBase):
    OPTION_LOG_STATUS_REPORT = 1 << 0
    OPTION_LOG_CREATE_ORDER = 1 << 1
    OPTION_LOG_ORDER_COMPLETED = 1 << 2
    OPTION_LOG_PROFITABILITY_STEP = 1 << 3
    OPTION_LOG_FULL_PROFITABILITY_STEP = 1 << 4
    OPTION_LOG_INSUFFICIENT_ASSET = 1 << 5
    OPTION_LOG_ALL = 0xfffffffffffffff

    @classmethod
    def logger(cls):
        global as_logger
        if as_logger is None:
            as_logger = logging.getLogger(__name__)
        return as_logger

    def init_params(self,
                    market_pairs: List[ArbitrageMarketPair],
                    min_profitability: Decimal,
					maxorder_amount: Decimal,
                    fee_amount: Decimal,
                    logging_options: int = OPTION_LOG_ORDER_COMPLETED,
                    status_report_interval: float = 60.0,
                    next_trade_delay_interval: float = 20,
                    failed_order_tolerance: int = 1,
                    use_oracle_conversion_rate: bool = True,
                    secondary_to_primary_base_conversion_rate: Decimal = Decimal("1"),
                    secondary_to_primary_quote_conversion_rate: Decimal = Decimal("1"),
                    hb_app_notification: bool = False):
        """
        :param market_pairs: list of arbitrage market pairs
        :param min_profitability: minimum profitability limit, for calculating arbitrage order sizes
		:param maxorder_amount: max order amount in usd for order
        :param logging_options: select the types of logs to output
        :param status_report_interval: how often to report network connection related warnings, if any
        :param next_trade_delay_interval: cool off period between trades
        :param failed_order_tolerance: number of failed orders to force stop the strategy when exceeded
        :param use_oracle_conversion_rate: Enables the use of the Oracle to get the price in ETH of each quote token to
        compare the trading pairs in between markets.
        If true the Oracle will be used. If false the reates will be fetched from uniswap. The default is false.
        :param secondary_to_primary_base_conversion_rate: Conversion rate of base token between markets. The default is 1
        :param secondary_to_primary_quote_conversion_rate: Conversion rate of quote token between markets. The default is 1
        :param hb_app_notification: Enables sending notifications to the client application. The default is false.
        """
        if len(market_pairs) < 0:
            raise ValueError(f"market_pairs must not be empty.")
        self._logging_options = logging_options
        self._market_pairs = market_pairs
        self._min_profitability = min_profitability
        self._maxorder_amount = maxorder_amount
        self._fee_amount = fee_amount
        self._all_markets_ready = False
        self._status_report_interval = status_report_interval
        self._last_timestamp = 0
        self._next_trade_delay = next_trade_delay_interval
        self._last_trade_timestamps = {}
        self._failed_order_tolerance = failed_order_tolerance
        self._cool_off_logged = False
        self._current_profitability = ()
        self._use_oracle_conversion_rate = use_oracle_conversion_rate
        self._secondary_to_primary_base_conversion_rate = secondary_to_primary_base_conversion_rate
        self._secondary_to_primary_quote_conversion_rate = secondary_to_primary_quote_conversion_rate
        self._last_order_logged = 0
        self._last_pair_update_logged = 0
        self._tradeflag = 0
        self._tradeid = 0
        self._mpaircycle = 0
        self._pricebuffer = Decimal(.5)
        self._tickcount = 0
        self._q1= Decimal(0)
        self._q2 = Decimal(0)
        self._q3 = Decimal(0)
        self._p1= Decimal(0)
        self._p2 = Decimal(0)
        self._p3 = Decimal(0)
        self._Trading_Dataset= []
        self._hb_app_notification = hb_app_notification
        self._maker_order_ids = []

        all_markets = []
        for x in self._market_pairs:
            for market_pair in x:
                all_markets.append(market_pair.first.market)
                all_markets.append(market_pair.second.market)
                all_markets.append(market_pair.third.market)

        self.c_add_markets(list(all_markets))

    @property
    def min_profitability(self) -> Decimal:
        return self._min_profitability
    
    @property
    def maxorder_amount(self) -> Decimal:
        return self._maxorder_amount
    
    @property
    def active_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(ex, order) for ex, order in self._sb_order_tracker.active_limit_orders
                if order.client_order_id in self._maker_order_ids]
    
    @property
    def active_bids(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_limit_orders if limit_order.is_buy]

    @property
    def active_asks(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_limit_orders if not limit_order.is_buy]
    
    @property
    def use_oracle_conversion_rate(self) -> Decimal:
        return self._use_oracle_conversion_rate

    @property
    def tracked_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.tracked_limit_orders

    @property
    def tracked_market_orders(self) -> List[Tuple[ExchangeBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    @property
    def tracked_limit_orders_data_frame(self) -> List[pd.DataFrame]:
        return self._sb_order_tracker.tracked_limit_orders_data_frame

    @property
    def tracked_market_orders_data_frame(self) -> List[pd.DataFrame]:
        return self._sb_order_tracker.tracked_market_orders_data_frame

    def format_status(self) -> str:
        return
        cdef:
            list lines = []
            list warning_lines = []
        for x in self._market_pairs:
            for market_pair in x:
                tracked_limit_orders = self.tracked_limit_orders
                tracked_market_orders = self.tracked_market_orders
        
                if len(tracked_limit_orders) > 0 or len(tracked_market_orders) > 0:
                    tracked_limit_orders_df = self.tracked_limit_orders_data_frame
                    tracked_market_orders_df = self.tracked_market_orders_data_frame
                    df_limit_lines = (str(tracked_limit_orders_df).split("\n")
                                      if len(tracked_limit_orders) > 0
                                      else list())
                    df_market_lines = (str(tracked_market_orders_df).split("\n")
                                       if len(tracked_market_orders) > 0
                                       else list())
                    lines.extend(["", "  Pending limit orders:"] +
                                 ["    " + line for line in df_limit_lines] +
                                 ["    " + line for line in df_market_lines])
                else:
                        lines.extend(["", "  No pending limit orders."])
        
                warning_lines.extend(self.balance_warning([market_pair.first, market_pair.second,market_pair.third]))

        if len(warning_lines) > 0:
            lines.extend(["", "  *** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            super().notify_hb_app(msg)
            
    def abdifffunc(self,quantity_list,index,quantity_current_1):
        absolute_difference_function_1 = lambda list_value_1 : abs(list_value_1 - quantity_current_1)
        closest_value_quantity_1 = min(quantity_list[index], key=absolute_difference_function_1)
        quantity_index_1 = quantity_list[index].index(closest_value_quantity_1)
        closest_value_price_1 = quantity_list[index+1][quantity_index_1] 
        return closest_value_price_1,quantity_index_1,quantity_current_1
     
    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.
        For tri arbitrage strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market pair to c_process_market_pair().
        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            list active_limit_orders = self.active_limit_orders
        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    self._tradeflag = 0
                    self._tickcount = 0
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No tri arbitrage trading is permitted.")
                    return
                else:
                    if self.OPTION_LOG_STATUS_REPORT:
                        self.logger().info(f"Markets are ready. Trading started.")

            if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                if should_report_warnings:
                    self.logger().warning(f"Markets are not all online. No tri arbitrage trading is permitted.")
                return
            
            # trades cannot be carried out in the first 20 seconds of starting the strategy
            if self._tickcount < 20:
                self._tradeflag = 0
            
            if self._tradeflag == 0:
                # when trade flag == 0 then check for profitability of current pairs.
                for market_pair in self._market_pairs:
                    # strategy is designed to work with several pairs of currencies at a time which are cycled through every tick, this is diabled for this version
                    self._Trading_Dataset,self._tradeflag,self._q1,self._q2,self._q3,self._p1,self._p2,self._p3,self._current_profitability = self.c_process_market_pair(market_pair[self._mpaircycle]) 
                    self._mpaircycle += 1
                    if self._mpaircycle >= len(market_pair):
                        self._mpaircycle = 0

                    if self._last_pair_update_logged + (60. * 20) < self._current_timestamp and self._tickcount > 20:
                        # output to app every 20 minutes profitability of arbitrage strategy if completed at that time
                        self.notify_hb_app(f"{market_pair[self._mpaircycle].first[1]} / {market_pair[self._mpaircycle].second[1]} / {market_pair[self._mpaircycle].third[1]} is currently trading at {round(self._current_profitability,3)}")
                        self._last_pair_update_logged = self._current_timestamp

                    if self._tradeflag != 0:
                        break
            else:
                # If there are active limit orders not yet completed wait till next tick for next trade
                if not self._sb_order_tracker.active_limit_orders:
                    # if tradeflag != 0 then make tradde. The tradeid will increase progressively as each trade is made
                    self._tradeid, self._tradeflag = self.c_maketrade(self._Trading_Dataset,self._tradeid,self._q1,self._q2,self._q3,self._p1,self._p2,self._p3,self._current_profitability)
            # log conversion rates every 5 minutes
            self._tickcount +=1

        finally:
            self._last_timestamp = timestamp

    cdef c_did_complete_buy_order(self, object buy_order_completed_event):
        """
        Output log for completed buy order.
        :param buy_order_completed_event: Order completed event
        """
        cdef:
            object buy_order = buy_order_completed_event
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(buy_order.order_id)
        if market_trading_pair_tuple is not None:
            self._last_trade_timestamps[market_trading_pair_tuple] = self._current_timestamp
            if self._logging_options & self.OPTION_LOG_ORDER_COMPLETED:
                self.log_with_clock(logging.INFO,
                                    f"Limit order completed on {market_trading_pair_tuple[0].name}: {buy_order.order_id}")
                self.notify_hb_app_with_timestamp(f"{buy_order.base_asset_amount:.8f} {buy_order.base_asset}-{buy_order.quote_asset} buy limit order completed on {market_trading_pair_tuple[0].name}")
                
    cdef c_did_complete_sell_order(self, object sell_order_completed_event):
        """
        Output log for completed sell order.
        :param sell_order_completed_event: Order completed event
        """
        cdef:
            object sell_order = sell_order_completed_event
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(sell_order.order_id)
        if market_trading_pair_tuple is not None:
            self._last_trade_timestamps[market_trading_pair_tuple] = self._current_timestamp
            if self._logging_options & self.OPTION_LOG_ORDER_COMPLETED:
                self.log_with_clock(logging.INFO,
                                    f"Limit order completed on {market_trading_pair_tuple[0].name}: {sell_order.order_id}")
                self.notify_hb_app_with_timestamp(f"{sell_order.base_asset_amount:.8f} {sell_order.base_asset}-{sell_order.quote_asset} sell limit order completed on {market_trading_pair_tuple[0].name}")

    cdef c_did_cancel_order(self, object cancel_event):
        """
        Output log for cancelled order.
        :param cancel_event: Order cancelled event.
        """
        cdef:
            str order_id = cancel_event.order_id
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        if market_trading_pair_tuple is not None:
            self.log_with_clock(logging.INFO,
                                f"Market order canceled on {market_trading_pair_tuple[0].name}: {order_id}")

    cdef tuple c_calculate_arbitrage_top_order_profitability(self, object market_pair):
        """
        Calculate the profitability of the triangular arbitrage strategy at that current time in all six possible directions, this is an estimate as only uses top prices.
        :param market_pair:
        :return: (double, double) that indicates profitability of arbitraging on each side
        """

        #Buy = False Sell= True
        fee = float(self._fee_amount)
        min_prof = self._min_profitability
        feer = (1-(fee/100))
        Bsum1 = 1
        Qsum1 = 1
        Qsum2 = 1
        
        # Grab top prices for buy and sell on all three pairs
        buy1p = float(market_pair.first.get_price(True))
        sell1p = float(market_pair.first.get_price(False))
        buy2p = float(market_pair.second.get_price(True))
        sell2p = float(market_pair.second.get_price(False))
        buy3p = float(market_pair.third.get_price(True))
        sell3p = float(market_pair.third.get_price(False))
        
        # Estimate profitability using only the top prices for each possible way
        Bat1 = (((sell2p*(Bsum1*sell1p*feer)*feer)/buy3p)*feer)
        Bat1p = (Bat1-Bsum1)/((Bat1+Bsum1)/2)*100
        Qat1 = (((sell3p*(Qsum1/buy1p*feer)*feer)/buy2p)*feer)
        Qat1p = (Qat1-Qsum1)/((Qat1+Qsum1)/2)*100
        Bat2 = ((((Qsum1*sell2p*feer)/buy3p*feer)*sell1p)*feer)
        Bat2p = (Bat2-Qsum1)/((Bat2+Qsum1)/2)*100
        Qat2 = ((((Qsum2/buy2p*feer)/buy1p*feer)*sell3p)*feer)
        Qat2p = (Qat2-Qsum2)/((Qat2+Qsum2)/2)*100
        Bat3 = ((((Bsum1*sell3p*feer)/buy2p*feer)/buy1p)*feer)
        Bat3p = (Bat3-Bsum1)/((Bat3+Bsum1)/2)*100
        Qat3 = ((((Qsum2/buy3p*feer)*sell1p*feer)*sell2p)*feer)
        Qat3p = (Qat3-Qsum2)/((Qat3+Qsum2)/2)*100
        
        # Find top profitability strategies (Usually 3)
        maxstrat = max(Bat1p,Qat1p,Bat2p,Qat2p,Bat3p,Qat3p)-0.001
        trade_strategy = []
        
        # Construct instruction list for making all trades
        if Bat1p > self._min_profitability and Bat1p > maxstrat:
            trade_strategy.append([market_pair.first,market_pair.second,market_pair.third,'sell','sell','buy',maxstrat,0])
            #Sell Base for Quote at 1, Sell base for quote at 2, Buy Base for quote at 3
        if Qat1p > self._min_profitability and Qat1p > maxstrat:
            trade_strategy.append([market_pair.first,market_pair.third,market_pair.second,'buy','sell','buy',maxstrat,0])
            #Buy Base for Quote at 1, Sell base for quote at 3, Buy Base for quote at 2
        if Bat2p > self._min_profitability and Bat2p > maxstrat:
            trade_strategy.append([market_pair.second,market_pair.third,market_pair.first,'sell','buy','sell',maxstrat,0])
            #Sell Base for Quote at 2, Buy base for quote at 3, Sell Base for quote at 1
        if Qat2p > self._min_profitability and Qat2p > maxstrat:
            trade_strategy.append([market_pair.second,market_pair.first,market_pair.third,'buy','buy','sell',maxstrat,0])
            #Buy Base for Quote at 2, Buy base for quote at 1, Sell Base for quote at 3
        if Bat3p > self._min_profitability and Bat3p > maxstrat:
            trade_strategy.append([market_pair.third,market_pair.second,market_pair.first,'sell','buy','buy',maxstrat,0])
            #Sell Base for Quote at 3, Buy base for quote at 2, Buy Base for quote at 1
        if Qat3p > self._min_profitability and Qat3p > maxstrat:
            trade_strategy.append([market_pair.third,market_pair.first,market_pair.second,'buy','sell','sell',maxstrat,0])
            #Buy Base for Quote at 3, Sell base for quote at 1, Sell Base for quote at 2

        if trade_strategy == []:
            return tuple(trade_strategy), Decimal(maxstrat)

        for x in range(len(trade_strategy)):
            # Find amount of assets available to the user for the first trade of all profitable strategies identified
            assets_df = self.wallet_balance_data_frame([trade_strategy[x][0]])
            if trade_strategy[x][3] == 'buy':
                qty_zero = assets_df['Available Balance'][1]
                base_pair_zero = f"{trade_strategy[x][0].quote_asset}-USDT"
            else:
                qty_zero = assets_df['Available Balance'][0]
                base_pair_zero = f"{trade_strategy[x][0].base_asset}-USDT"
            try:
                base_rate_zero = RateOracle.get_instance().rate(base_pair_zero)
                qty_usd = (Decimal(qty_zero) * base_rate_zero)
                trade_strategy[x][7] = qty_usd
            except:
                if len(trade_strategy) > 1:
                    return tuple(trade_strategy[0]), Decimal(maxstrat)
                else:
                    return tuple(trade_strategy), Decimal(maxstrat)
        # find the most profitable strategy with most amount of starting assets.
        max_row = max([sublist[-1] for sublist in trade_strategy])
        max_index = [sublist[-1] for sublist in trade_strategy].index(max_row)
        # Return the instructions for the trades and the initial estimated profitability
        return tuple(trade_strategy[max_index]), Decimal(maxstrat)

    cdef bint c_ready_for_new_orders(self, list market_trading_pair_tuples):
        """
        Check whether we are ready for making new arbitrage orders or not. Conditions where we should not make further
        new orders include:

         1. There are outstanding limit taker orders.
         2. We're still within the cool-off period from the last trade, which means the exchange balances may be not
            accurate temporarily.

        If none of the above conditions are matched, then we're ready for new orders.

        :param market_trading_pair_tuples: list of arbitrage market pairs
        :return: True if ready, False if not
        """
        cdef:
            double time_left
            dict tracked_taker_orders = {**self._sb_order_tracker.c_get_limit_orders(), ** self._sb_order_tracker.c_get_market_orders()}

        for market_trading_pair_tuple in market_trading_pair_tuples:
            # Do not continue if there are pending limit order
            if len(tracked_taker_orders.get(market_trading_pair_tuple, {})) > 0:
                return False
            # Wait for the cool off interval before the next trade, so wallet balance is up to date
            ready_to_trade_time = self._last_trade_timestamps.get(market_trading_pair_tuple, 0) + self._next_trade_delay
            if market_trading_pair_tuple in self._last_trade_timestamps and ready_to_trade_time > self._current_timestamp:
                time_left = self._current_timestamp - self._last_trade_timestamps[market_trading_pair_tuple] - self._next_trade_delay
                if not self._cool_off_logged:
                    self.log_with_clock(
                        logging.INFO,
                        f"Cooling off from previous trade on {market_trading_pair_tuple.market.name}. "
                        f"Resuming in {int(time_left)} seconds."
                    )
                    self._cool_off_logged = True
                return False

        if self._cool_off_logged:
            self.log_with_clock(
                logging.INFO,
                f"Cool off completed. Arbitrage strategy is now ready for new orders."
            )
            # reset cool off log tag when strategy is ready for new orders
            self._cool_off_logged = False

        return True


    cdef c_process_market_pair(self, object market_pair):
        """
        Checks the estimated profitability of all possible triangular arbitrage strategies using c_calculate_arbitrage_top_order_profitability and then if profitability 
        meets min profitability requirement assesses it further and makes trade using c_process_market_pair_inner.
        :param market_pair: arbitrage market pair
        """

        Trade_Dataset, self._current_profitability = \
            self.c_calculate_arbitrage_top_order_profitability(market_pair)

        if Trade_Dataset == []:
            return Trade_Dataset, 0, 0, 0, 0, 0, 0, 0, self._current_profitability
        
        if self._current_profitability < self._min_profitability:
            return Trade_Dataset, 0, 0, 0, 0, 0, 0, 0, self._current_profitability
        
        if not self.c_ready_for_new_orders([market_pair.first,market_pair.second,market_pair.third]):
            return Trade_Dataset, 0, 0, 0, 0, 0, 0, 0, self._current_profitability

        Trading_Dataset, tradeflag, q1, q2, q3, p1, p2, p3,best_profitability = self.c_process_market_pair_inner(Trade_Dataset)
        
        return Trading_Dataset, tradeflag, q1, q2, q3, p1, p2, p3,best_profitability
    
    cdef c_process_market_pair_inner(self, object Trading_Dataset):
        """
        Uses c_find_best_profitable_amount to assess the actual profitability taking into account the order size and actual VWAP prices.
        :type buy_market_trading_pair_tuple: MarketTradingPairTuple
        :type sell_market_trading_pair_tuple: MarketTradingPairTuple
        """
        cdef:
            object quantized_buy_amount
            object quantized_sell_amount
            object quantized_order_amount
            object first_quantity = s_decimal_0  # best profitable order amount
            object second_quantity = s_decimal_0 
            object third_quantity = s_decimal_0 
            object best_profitability = s_decimal_0  # best profitable order amount
            ExchangeBase first_market = Trading_Dataset[0].market
            ExchangeBase second_market = Trading_Dataset[1].market
            ExchangeBase third_market = Trading_Dataset[2].market
            
        first_quantity, second_quantity, third_quantity, first_price, second_price, third_price,best_profitability  = self.c_find_best_profitable_amount(Trading_Dataset)

        quantized_first_amount = first_market.c_quantize_order_amount(Trading_Dataset[0].trading_pair, Decimal(first_quantity), Decimal(first_price))
        quantized_second_amount = (quantized_first_amount / first_quantity) * second_quantity
        quantized_third_amount = (quantized_first_amount / first_quantity) * third_quantity
        quantized_order_amount = min(quantized_first_amount, quantized_second_amount, quantized_third_amount)
        
        if quantized_order_amount == Decimal(0):
            quantized_first_amount = first_quantity
            quantized_second_amount = second_quantity
            quantized_third_amount = third_quantity
            quantized_order_amount = min(quantized_first_amount, quantized_second_amount, quantized_third_amount)

        if best_profitability < self._min_profitability or quantized_order_amount == Decimal(0):
            return Trading_Dataset, 0, quantized_first_amount, quantized_second_amount, quantized_third_amount, first_price, second_price, third_price,best_profitability
        else:
            # The calculated profitabilities are greater than the required min profitability and everything is ready to make the trade! Trade flag is set to 1 for the next tick.
            return Trading_Dataset, 1, quantized_first_amount, quantized_second_amount, quantized_third_amount, first_price, second_price, third_price,best_profitability
        
    cdef c_maketrade(self, object Trading_Dataset, tradeid,quantized_first_amount, quantized_second_amount, quantized_third_amount, first_price, second_price, third_price, best_profitability):
        # Ready to make trades as tradeflag is 1, tradeid starts at 0 (First trade) and incrases to 2 (Third trade). On third trade tradeid and tradeflag are set back to 0
        first_order_type = Trading_Dataset[0].market.get_taker_order_type()
        second_order_type = Trading_Dataset[1].market.get_taker_order_type()
        third_order_type = Trading_Dataset[2].market.get_taker_order_type()
        
        if tradeid == 0:
            if self._last_order_logged + (60. * 5) > self._current_timestamp:
            # Only allow trades every 5 minutes
                return 0,0
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                self.log_with_clock(logging.INFO,
                                    f"Executing limit order {Trading_Dataset[3]} of {Trading_Dataset[0].trading_pair} "
                                    f"at {Trading_Dataset[0].market.name} at price {first_price} with {quantized_first_amount} "
                                    f" and {Trading_Dataset[4]} of {Trading_Dataset[1].trading_pair} "
                                    f"at {Trading_Dataset[1].market.name} at price {second_price}  with {quantized_second_amount}"
                                    f" and {Trading_Dataset[5]} of {Trading_Dataset[2].trading_pair} "
                                    f"at {Trading_Dataset[2].market.name} at price {third_price}  with {quantized_third_amount}"
                                    f" with profitability of {best_profitability}")
            if Trading_Dataset[3] == 'buy':
                self.c_buy_with_specific_market(Trading_Dataset[0], quantized_first_amount, order_type=first_order_type, price=first_price*(Decimal(1)+(self._pricebuffer/100)), expiration_seconds=self._next_trade_delay)
                self.notify_hb_app(" Buy  1: " + str(Trading_Dataset[0]) + " " + str(quantized_first_amount))
            elif Trading_Dataset[3] == 'sell':
                self.c_sell_with_specific_market(Trading_Dataset[0], quantized_first_amount,order_type=first_order_type, price=first_price*(Decimal(1)-(self._pricebuffer/100)), expiration_seconds=self._next_trade_delay)
                self.notify_hb_app(" Sell 1: " + str(Trading_Dataset[0]) + " " + str(quantized_first_amount))
            # Trading mode active and ready for second trade
            return 1,1
        if tradeid == 1:
            if Trading_Dataset[4] == 'buy':
                self.c_buy_with_specific_market(Trading_Dataset[1], quantized_second_amount,order_type=second_order_type, price=second_price*(Decimal(1)+(self._pricebuffer/100)), expiration_seconds=self._next_trade_delay)
                self.notify_hb_app(" Buy 2: " + str(Trading_Dataset[1]) + " " + str(quantized_second_amount))
            elif Trading_Dataset[4] == 'sell':
                self.c_sell_with_specific_market(Trading_Dataset[1], quantized_second_amount,order_type=second_order_type, price=second_price*(Decimal(1)-(self._pricebuffer/100)), expiration_seconds=self._next_trade_delay)
                self.notify_hb_app(" Sell 2: " + str(Trading_Dataset[1]) + " " + str(quantized_second_amount))
            # Trading mode active and ready for third trade
            return 2,1
        if tradeid == 2:
            if Trading_Dataset[5] == 'buy':
                self.c_buy_with_specific_market(Trading_Dataset[2], quantized_third_amount,order_type=third_order_type, price=third_price*(Decimal(1)+(self._pricebuffer/100)), expiration_seconds=self._next_trade_delay)
                self.notify_hb_app(" Buy 3: " + str(Trading_Dataset[2]) + " " + str(quantized_third_amount)+ " " + str(best_profitability))
            elif Trading_Dataset[5] == 'sell':
                self.c_sell_with_specific_market(Trading_Dataset[2], quantized_third_amount,order_type=third_order_type, price=third_price*(Decimal(1)-(self._pricebuffer/100)), expiration_seconds=self._next_trade_delay)
                self.notify_hb_app(" Sell 3: " + str(Trading_Dataset[2]) + " " + str(quantized_third_amount)+ " " + str(best_profitability))
            self.logger().info(self.format_status())
            # Trading mode inactive ready for first trade
            self._last_order_logged = self._current_timestamp
            return 0,0

    def orderbook_vwap_price_volume(self,order_book,qty_req,dir_v,type_v,price_quantum):
        try:
            # Calculates the VWAP or simply corresponding price by volume from a list of order book orders and prices from a known order volume, if keyword vwap is used 
            # in type_v then the average volume weighted price will be returned, alternatively if price is used instead then the top price corresponding to 
            # that cumulative volume in the order book will be returned. dir_v keyword 1 will return the nearest price towards the mid amrket, keywork -1 will
            # return the nearest price away from mid market and 0 will return the calculated price.
            # offset percentage positive offsets price towards mid market negative offsets away.
            ob_iter = next(order_book)
            qty_cum = [ob_iter.amount]
            pr_ex = [ob_iter.price]
            pr_vwap = [ob_iter.price]
            a = 0
            while True:
                if qty_cum[-1] > qty_req and a==0:
                    qty_cum[-1] = qty_req
                    break
                
                ob_iter = next(order_book)
                qty_cum.append(ob_iter.amount + qty_cum[-1])
        
                if qty_cum[-1] > qty_req and a>0:
                    adj_q = qty_cum[-1] - qty_req
                    pr_vwap.append(((ob_iter.price*(ob_iter.amount-adj_q))+(pr_vwap[a]*qty_cum[a]))/(qty_cum[a]+(ob_iter.amount-adj_q)))
                    pr_ex.append(ob_iter.price)
                    qty_cum[-1] = qty_req
                    break
                
                pr_vwap.append(((ob_iter.price*ob_iter.amount)+(pr_vwap[a]*qty_cum[a]))/(qty_cum[a]+ob_iter.amount))
                pr_ex.append(ob_iter.price)
                    
                a += 1
        
            res_pr_cum = Decimal(pr_vwap[-1])
            res_pr = Decimal(pr_ex[-1])
     
            # Using resultant prices for either VWAP or price round up or down to nearest tick
            if dir_v == 1:
                if pr_ex[0] < res_pr_cum: # Asks
                    res_pr_cum = (round(res_pr_cum / price_quantum)-Decimal(1)) * price_quantum
                    res_pr = (round(res_pr / price_quantum)-Decimal(1)) * price_quantum
                elif pr_ex[0] > res_pr_cum: # Bids
                    res_pr_cum = (round(res_pr_cum / price_quantum)+Decimal(1)) * price_quantum
                    res_pr = (round(res_pr / price_quantum)+Decimal(1)) * price_quantum
            if dir_v == -1:
                if pr_ex[0] < res_pr_cum:# Asks
                    res_pr_cum = (round(res_pr_cum / price_quantum)+Decimal(1)) * price_quantum
                    res_pr = (round(res_pr / price_quantum)+Decimal(1)) * price_quantum
                elif pr_ex[0] > res_pr_cum:# Bids
                    res_pr_cum = (round(res_pr_cum / price_quantum)-Decimal(1)) * price_quantum
                    res_pr = (round(res_pr / price_quantum)-Decimal(1)) * price_quantum
            if type_v == 'vwap':
                return Decimal(res_pr_cum)
            else:
                return Decimal(res_pr)
        except:
            return(Decimal(0))
        
    cdef tuple c_find_best_profitable_amount(self, object trade_strategy):
        """
        Given a buy market and a sell market, calculate the optimal order size for the buy and sell orders on all
        markets and the profitability ratio. This function accounts for trading fees required by both markets before
        arriving at the optimal order size and profitability ratio.
        :param buy_market_trading_pair_tuple: trading pair for buy side
        :param sell_market_trading_pair_tuple: trading pair for sell side
        :return: (order size, profitability ratio, bid_price, ask_price)
        :rtype: Tuple[float, float, float, float]
        """
        cdef:
            object total_bid_value = s_decimal_0  # total revenue
            object total_ask_value = s_decimal_0  # total cost
            object total_bid_value_adjusted = s_decimal_0  # total revenue adjusted with exchange rate conversion
            object total_ask_value_adjusted = s_decimal_0  # total cost adjusted with exchange rate conversion
            object total_previous_step_base_amount = s_decimal_0
            object bid_price = s_decimal_0  # bid price
            object ask_price = s_decimal_0  # ask price
            object profitability
            object best_profitable_order_amount = s_decimal_0
            object best_profitable_order_profitability = s_decimal_0
            object buy_fee
            object sell_fee
            object total_sell_flat_fees
            object total_buy_flat_fees
            object quantized_profitable_base_amount
            object net_sell_proceeds
            object net_buy_costs
            object first_market_quote_balance
            object second_market_base_balance
            object third_market_base_balance
            object step_amount = s_decimal_0
            object first_leftover_amount = s_decimal_0
            object second_leftover_amount = s_decimal_0
            object third_leftover_amount = s_decimal_0
            object current_first = None
            object current_second = None
            object current_third = None
            object current_first_price_adjusted
            object current_second_price_adjusted
            object current_third_price_adjusted

        fee = float(self._fee_amount)
        quantity_list = [[],[],[],[],[],[]]
        result_list = [[],[],[],[],[],[]] #Quantity 1, Quantity 2, Quantity 3, Price 1, Price 2, price 3
        # Find the max order amount in actual currency using usd figure from program variables
        base_pair_first = f"{trade_strategy[0].base_asset}-USDT"
        base_rate_first = RateOracle.get_instance().rate(base_pair_first)
        quantity_base = (self._maxorder_amount / base_rate_first) * Decimal(1/20) 
        quantity_current_1 = quantity_base
        quantity_start_amount = quantity_base
        #Using the VWAP price list and corresponding order sizes previousely made starting at 1/20th of the max order size and increasing by 1/20th each iteration simulate the resulting profitability  .
        i = 0
        while i < 20:
            for x in range(0, 6, 2):
                # Simulate the three trades and starting and ending balance
                if x == 0:
                    quantity_diff_start = quantity_current_1
                if trade_strategy[int(x/2)+3] == 'sell':
                    start_quantity = quantity_current_1 #Base
                    price_vwap = self.orderbook_vwap_price_volume(trade_strategy[int(x/2)].order_book_bid_entries(),quantity_current_1,0,'vwap','NA')
                    end_quantity = quantity_current_1 * (price_vwap * (1-(Decimal(fee)/100)))
                    base_qty = start_quantity
                    #self.notify_hb_app(str(i) + ": Sell 1 Pair: " + str(trade_strategy[int(x/2)].trading_pair) + " Price: " + str(float(price_vwap)) + " Qty: " + str(float(base_qty)))
                else:
                    if x == 0:
                        price_vwap = self.orderbook_vwap_price_volume(trade_strategy[int(x/2)].order_book_ask_entries(),quantity_current_1,0,'vwap','NA')
                        end_quantity = quantity_current_1
                        start_quantity = quantity_current_1 * (price_vwap * (1+(Decimal(fee)/100)))
                        quantity_diff_start = start_quantity
                        base_qty = end_quantity
                        #self.notify_hb_app(str(i) + ": Buy 2 Pair: " + str(trade_strategy[int(x/2)].trading_pair) + " Price: " + str(float(price_vwap)) + " Qty: " + str(float(base_qty)))
                    else:
                        base_rate_ex = RateOracle.get_instance().rate(trade_strategy[int(x/2)].trading_pair)
                        start_quantity = quantity_current_1 
                        base_est = quantity_current_1 / base_rate_ex
                        price_vwap = self.orderbook_vwap_price_volume(trade_strategy[int(x/2)].order_book_ask_entries(),base_est,0,'vwap','NA')                        
                        end_quantity = quantity_current_1 / (price_vwap* (1+(Decimal(fee)/100))) #Base
                        base_qty = end_quantity
                        #self.notify_hb_app(str(i) + ": Buy 3 Pair: " + str(trade_strategy[int(x/2)].trading_pair) + " Price: " + str(float(price_vwap)) + " Qty: " + str(float(base_qty)))

                quantity_current_1 = end_quantity
                result_list[int(x/2)+3] = price_vwap
                result_list[int(x/2)] = base_qty
            #if i > 0:
            #    self.notify_hb_app(str(i) + ": Pair: " + str(trade_strategy[0].trading_pair) + " Price: " + str(float(price_vwap)) + " Qty: " + str(float(base_qty)) + " Prev Qty: " + str(float(quantity_diff))+ " Prev Qty Diff: " + str(float(quantity_current_1 - quantity_diff_start))+ " Percentage: " + str(((quantity_current_1 - quantity_diff_start)/quantity_current_1)*100))
            # If the resulting profitability is less than the previous iteration then go with the previous iterations results.
            if i>0 and quantity_diff > quantity_current_1 - quantity_diff_start:
                return result_list[0], result_list[1],result_list[2],result_list[3],result_list[4],result_list[5],quantity_per
            
            quantity_diff = quantity_current_1 - quantity_diff_start
            quantity_per = ((quantity_diff/quantity_current_1)*100)
            quantity_start_amount += quantity_base
            quantity_diff_start = quantity_start_amount
            quantity_current_1 = quantity_start_amount
            #if quantity_current_1 - quantity_base < quantity_diff:
            i += 1
        # Otherwise go with the last iteration i.e the full order amount.
        return result_list[0], result_list[1],result_list[2],result_list[3],result_list[4],result_list[5],quantity_per

    def ready_for_new_orders(self, market_pair):
        return self.c_ready_for_new_orders(market_pair)
    # ---------------------------------------------------------------
