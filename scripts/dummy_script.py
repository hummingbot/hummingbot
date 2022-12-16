from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import BuyOrderCompletedEvent, SellOrderCompletedEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DummyScript(ScriptStrategyBase):
    order_amount = Decimal(0.1)   # This can be adjusted
    order_refresh_time = 10   # This can be adjusted
    create_timestamp = 0

    trading_pair = "BTC-USDT"   # This can be adjusted

    high_liquidity_exchange = "binance_paper_trade"   # This can be adjusted
    low_liquidity_exchange = "gate_io_paper_trade"   # This can be adjusted
    markets = {high_liquidity_exchange: {trading_pair},
               low_liquidity_exchange: {trading_pair}
               }

    # These 2 attributes are used to keep track of the amount of open orders on the low liquidity exchange
    buy_orders_on_low_liquidity_exchange = 0
    sell_orders_on_low_liquidity_exchange = 0

    # These 2 attributes have a default value of False. When there is an order filled on the low liquidity exchange
    # it will be set to True so the bot knows it should place a hedge order on the high liquidity exchange
    buy_order_completed = False
    sell_order_completed = False

    # this will be used to calculate the price for the hedge order on the high liquidity exchange:
    spread_bps = 10
    min_spread_bps = 0

    def on_tick(self):
        """Check if orders need to be refreshed. If yes we need to cancel all orders, calculate new price and amount and place
        new maker orders on the low liquidity exchange. If no than we need to check that we have maker orders on both
        bid and ask side. We also need to check if an order got filled. If yes than we need the bot to place a hedge
        order on the high liq ex. We also want the bot to check the balances and send a notification if an available
        balance runs low."""
        # Low liquidity exchange side
        # Do we need to refresh orders?
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal = self.create_proposal_based_on_high_liquidity_exchange_price()
            adjusted_proposal = self.adjust_proposal_to_budget(proposal)
            self.place_orders(adjusted_proposal, self.low_liquidity_exchange)
            # Update timestamp
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

        # Are there less than 1 buy or sell order on the exchange?
        elif self.sell_orders_on_low_liquidity_exchange < 1 or self.buy_orders_on_low_liquidity_exchange < 1:
            self.cancel_all_orders()
            proposal = self.create_proposal_based_on_high_liquidity_exchange_price()
            adjusted_proposal = self.adjust_proposal_to_budget(proposal)
            self.place_orders(adjusted_proposal, self.low_liquidity_exchange)
            # Update timestamp
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

        # High liquidity exchange side
            # If spread to low than we need to cancel and replace order
        for order in self.get_active_orders(connector_name=self.high_liquidity_exchange):
            if OrderType.LIMIT:
                if order.is_buy:
                    low_liquidity_exchange_sell_result = self.low_liquidity_connector().get_price_for_volume(
                        self.trading_pair, False, self.order_amount)
                    buy_cancel_threshold = low_liquidity_exchange_sell_result.result_price * Decimal(
                        1 - self.min_spread_bps / 10000)
                    if order.price > buy_cancel_threshold:
                        self.cancel(self.high_liquidity_exchange, order.trading_pair, order.client_order_id)
                        volatility = self.calculate_spreads_and_volatility()
                        hedge = self.determine_hedge_sell_order_price(volatility)
                        adjusted_hedge = self.adjust_hedge_to_budget(hedge)
                        self.place_orders(adjusted_hedge, self.high_liquidity_exchange)
                else:
                    high_liquidity_exchange_buy_result = self.high_liquidity_connector().get_price_for_volume(
                        self.trading_pair, True, self.order_amount)
                    sell_cancel_threshold = high_liquidity_exchange_buy_result.result_price * Decimal(
                        1 + self.min_spread_bps / 10000)
                    if order.price < sell_cancel_threshold:
                        self.cancel(self.high_liquidity_exchange, order.trading_pair, order.client_order_id)
                        volatility = self.calculate_spreads_and_volatility()
                        hedge = self.determine_hedge_buy_order_price(volatility)
                        adjusted_hedge = self.adjust_hedge_to_budget(hedge)
                        self.place_orders(adjusted_hedge, self.high_liquidity_exchange)

        # If an order got hit on the low liquidity exchange than we need to hedge
        if self.buy_order_completed:
            self.buy_orders_on_low_liquidity_exchange -= 1
            volatility = self.calculate_spreads_and_volatility()
            hedge = self.determine_hedge_sell_order_price(volatility)
            adjusted_hedge = self.adjust_hedge_to_budget(hedge)
            self.place_orders(adjusted_hedge, self.high_liquidity_exchange)

        elif self.sell_order_completed:
            self.sell_orders_on_low_liquidity_exchange -= 1
            volatility = self.calculate_spreads_and_volatility()
            hedge = self.determine_hedge_buy_order_price(volatility)
            adjusted_hedge = self.adjust_hedge_to_budget(hedge)
            self.place_orders(adjusted_hedge, self.high_liquidity_exchange)

        # Check balances and notify when balance is low
        list_of_data = self.get_balance_df().to_dict("split")["data"]
        # list of data is a list containing nested list that contain all the elements of 1 row of the dataframe in
        # the following order [exchange, asset, total balance, available balance].
        # To check the available balance we loop through each list and identify the necessary variables.
        for data in list_of_data:
            exchange = data[0]
            asset = data[1]
            available_balance = data[3]

            if asset == "BTC":
                if available_balance < 0.2:
                    message = f"Available balance for {asset} on {exchange} is {available_balance} {asset} and should " \
                              f"be adjusted. "
                    self.notify_hb_app(message)

            elif asset == "USDT":
                if available_balance < 200:
                    message = f"Available balance for {asset} on {exchange} is {available_balance} {asset} and should " \
                              f"be adjusted. "
                    self.notify_hb_app(message)

    # instead of using def maker_connector and taker_connector I want to rename it high_liquidity_connector and
    # low_liquidity_connector because on the high liquidity exchange we will be taker or maker depending on the
    # volatility
    def high_liquidity_connector(self):
        return self.connectors[self.high_liquidity_exchange]

    def low_liquidity_connector(self):
        return self.connectors[self.low_liquidity_exchange]

    # All methods concerning the low liquidity exchange
    def cancel_all_orders(self):
        """Cancel all orders on the low liquidity exchange"""
        orders = self.get_active_orders(connector_name=self.low_liquidity_exchange)
        for order in orders:
            self.cancel(connector_name=self.low_liquidity_exchange,
                        trading_pair=order.trading_pair,
                        order_id=order.client_order_id)
        # Set number of orders back to 0:
        self.buy_orders_on_low_liquidity_exchange = 0
        self.sell_orders_on_low_liquidity_exchange = 0

    def create_proposal_based_on_high_liquidity_exchange_price(self):
        """Determine best ask and bid price by fetching the necessary data from the hedging exchange (=high liquidity exchang)
        , calculate order_amount, then create a buy and sell order-candidate"""
        # Using the logic of xemm example to calculate the buy and sell price on the low liquidity exchange.
        high_liquidity_exchange_buy_result = self.high_liquidity_connector().get_price_for_volume(self.trading_pair,
                                                                                                  True,
                                                                                                  self.order_amount)
        high_liquidity_exchange_sell_result = self.high_liquidity_connector().get_price_for_volume(self.trading_pair,
                                                                                                   False,
                                                                                                   self.order_amount)

        low_liquidity_exchange_buy_price = high_liquidity_exchange_sell_result.result_price * Decimal(
            1 - self.spread_bps / 10000)
        low_liquidity_exchange_sell_price = high_liquidity_exchange_buy_result.result_price * Decimal(
            1 + self.spread_bps / 10000)

        buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(self.order_amount),
                                   price=low_liquidity_exchange_buy_price)
        sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.order_amount),
                                    price=low_liquidity_exchange_sell_price)

        return buy_order, sell_order

    def adjust_proposal_to_budget(self, proposal):
        """Adjust the order-candidate to the available budget"""
        proposal_adjusted = self.connectors[self.low_liquidity_exchange].budget_checker.adjust_candidates(
            proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, adjusted_proposal, exchange):
        """For each order in the adjusted proposal (= adjusted order-candidates)-> use method place_order()"""
        if exchange == self.low_liquidity_exchange:
            for order in adjusted_proposal:
                self.place_order(connector_name=self.low_liquidity_exchange, order=order)
        elif exchange == self.high_liquidity_exchange:
            for order in adjusted_proposal:
                self.place_order(connector_name=self.high_liquidity_exchange, order=order)

    def place_order(self, connector_name, order):
        """Places buy and sell orders."""
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
            # Add orders to the variable that keeps track of the number of orders on the exchange:
            if connector_name == self.low_liquidity_exchange:
                self.sell_orders_on_low_liquidity_exchange += 1
            elif connector_name == self.high_liquidity_exchange:
                self.buy_order_completed = False

        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
            # Add orders to the variable that keeps track of the number of orders on the exchange:
            if connector_name == self.low_liquidity_exchange:
                self.buy_orders_on_low_liquidity_exchange += 1
            elif connector_name == self.high_liquidity_exchange:
                self.sell_order_completed = False

    # Methods concerning the high liquidity exchange
    def calculate_spreads_and_volatility(self):
        best_ask = self.connectors[self.high_liquidity_exchange].get_price(self.trading_pair, is_buy=True)
        best_bid = self.connectors[self.high_liquidity_exchange].get_price(self.trading_pair, is_buy=False)

        bid_ask_spread_bps = (best_ask - best_bid) * 10000

        if bid_ask_spread_bps > 15:  # This can be adjusted
            volatility = "high"
        else:
            volatility = "low"
        return volatility

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        # switch the variable to true
        self.buy_order_completed = True

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        # switch the variable to true
        self.sell_order_completed = True

    def determine_hedge_sell_order_price(self, volatility):
        # We want the hedge to be placed on the best_ask. On_tick the bot will check if at this order.price the spread
        # is too low (in case the order is a limit order).
        best_ask = self.high_liquidity_exchange.get_price(self.trading_pair, is_buy= True)

        if volatility == "high":
            hedge_sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                              order_side=TradeType.SELL, amount=Decimal(self.order_amount),
                                              price=best_ask)
        elif volatility == "low":
            hedge_sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=False,
                                              order_type=OrderType.MARKET,
                                              order_side=TradeType.SELL, amount=Decimal(self.order_amount),
                                              price=best_ask)
        return hedge_sell_order

    def determine_hedge_buy_order_price(self, volatility):
        # We want the hedge to be placed on the best_bid. On_tick the bot will check if at this order.price the spread
        # is too low (in case the order is a limit order).
        best_bid = self.high_liquidity_exchange.get_price(self.trading_pair, is_buy= True)

        if volatility == "high":
            hedge_buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                             order_side=TradeType.BUY, amount=Decimal(self.order_amount),
                                             price=best_bid)
        elif volatility == "low":
            hedge_buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=False,
                                             order_type=OrderType.MARKET,
                                             order_side=TradeType.BUY, amount=Decimal(self.order_amount),
                                             price=best_bid)
        return hedge_buy_order

    def adjust_hedge_to_budget(self, hedge):
        """Adjust the hedge order-candidate to the available budget"""
        hedge_adjusted = self.connectors[self.low_liquidity_exchange].budget_checker.adjust_candidates(hedge,
                                                                                                       all_or_none=True)
        return hedge_adjusted

    # For format status
    def exchanges_df(self) -> pd.DataFrame:
        """
        Return a custom data frame of prices on maker vs taker exchanges for display purposes
        """
        mid_price = self.connectors[self.low_liquidity_exchange].get_mid_price(self.trading_pair)
        low_liquidity_exchange_buy_result = self.connectors[self.low_liquidity_exchange].get_price_for_volume(
            self.trading_pair, True,
            self.order_amount)
        low_liquidity_exchange_sell_result = self.connectors[self.low_liquidity_exchange].get_price_for_volume(
            self.trading_pair, False,
            self.order_amount)
        high_liquidity_exchange_buy_result = self.connectors[self.high_liquidity_exchange].get_price_for_volume(
            self.trading_pair, True,
            self.order_amount)
        high_liquidity_exchange_sell_result = self.connectors[self.high_liquidity_exchange].get_price_for_volume(
            self.trading_pair, False,
            self.order_amount)
        maker_buy_spread_bps = (low_liquidity_exchange_buy_result.result_price -
                                high_liquidity_exchange_buy_result.result_price) / mid_price * 10000
        maker_sell_spread_bps = (high_liquidity_exchange_sell_result.result_price -
                                 low_liquidity_exchange_buy_result.result_price) / mid_price * 10000

        columns = ["Exchange", "Market", "Mid Price", "Buy Price", "Sell Price", "Buy Spread", "Sell Spread"]
        data = [[
            self.low_liquidity_exchange,
            self.trading_pair,
            float(self.connectors[self.low_liquidity_exchange].get_mid_price(self.trading_pair)),
            float(low_liquidity_exchange_buy_result.result_price),
            float(low_liquidity_exchange_sell_result.result_price),
            int(maker_buy_spread_bps),
            int(maker_sell_spread_bps)
        ], [
            self.high_liquidity_exchange,
            self.trading_pair,
            float(self.connectors[self.high_liquidity_exchange].get_mid_price(self.trading_pair)),
            float(high_liquidity_exchange_buy_result.result_price),
            float(high_liquidity_exchange_sell_result.result_price),
            int(-maker_buy_spread_bps),
            int(-maker_sell_spread_bps)
        ]]

        df = pd.DataFrame(data=data, columns=columns)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        """
        Returns a custom data frame of all active maker orders for display purposes
        """
        columns = ["Exchange", "Market", "Side", "Price", "Amount", "Spread Mid", "Spread Cancel", "Age"]
        data = []
        mid_price = self.connectors[self.low_liquidity_exchange].get_mid_price(self.trading_pair)
        high_liquidity_exchange_buy_result = self.connectors[self.high_liquidity_exchange].get_price_for_volume(
            self.trading_pair, True,
            self.order_amount)
        high_liquidity_exchange_sell_result = self.connectors[self.high_liquidity_exchange].get_price_for_volume(
            self.trading_pair, False,
            self.order_amount)
        buy_cancel_threshold = high_liquidity_exchange_sell_result.result_price * Decimal(
            1 - self.min_spread_bps / 10000)
        sell_cancel_threshold = high_liquidity_exchange_buy_result.result_price * Decimal(
            1 + self.min_spread_bps / 10000)
        for connector_name, connector in self.connectors.items():
            for order in self.get_active_orders(connector_name):
                age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
                spread_mid_bps = (mid_price - order.price) / mid_price * 10000 if order.is_buy else \
                    (order.price - mid_price) / mid_price * 10000
                spread_cancel_bps = (buy_cancel_threshold - order.price) / buy_cancel_threshold * 10000 if \
                    order.is_buy else (order.price - sell_cancel_threshold) / sell_cancel_threshold * 10000
                data.append([
                    self.low_liquidity_exchange,
                    order.trading_pair,
                    "buy" if order.is_buy else "sell",
                    float(order.price),
                    float(order.quantity),
                    int(spread_mid_bps),
                    int(spread_cancel_bps),
                    age_txt
                ])

        if not data:
            raise ValueError
        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Market", "Side"], inplace=True)
        return df

    def format_status(self) -> str:
        """Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output."""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        exchanges_df = self.exchanges_df()
        lines.extend(["", "  Exchanges:"] + ["    " + line for line in exchanges_df.to_string(index=False).split("\n")])

        try:
            orders_df = self.active_orders_df()
            lines.extend(
                ["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        return "\n".join(lines)
