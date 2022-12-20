from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DummyScript(ScriptStrategyBase):
    min_base_asset = 0.2
    min_quote_asset = 200

    order_amount = Decimal(0.5)  # This can be adjusted
    order_refresh_time = 10  # This can be adjusted
    create_timestamp = 0

    base_asset = "BTC"  # This can be adjusted
    quote_asset = "USDT"  # This can be adjusted
    trading_pair = f"{base_asset}-{quote_asset}"

    high_liquidity_exchange = "binance_paper_trade"  # This can be adjusted
    low_liquidity_exchange = "gate_io_paper_trade"  # This can be adjusted
    markets = {high_liquidity_exchange: {trading_pair},
               low_liquidity_exchange: {trading_pair}
               }

    # These 2 attributes are used to keep track of the amount of open orders on the low liquidity exchange
    buy_orders_on_low_liquidity_exchange = 0
    sell_orders_on_low_liquidity_exchange = 0

    # this will be used to calculate the price for the hedge order on the high liquidity exchange:
    spread_bps = 5
    min_spread_bps = 0

    def high_liquidity_connector(self):
        return self.connectors[self.high_liquidity_exchange]

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
            self.place_orders(adjusted_proposal)
            # Update timestamp
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

        # Are there less than 1 buy or sell order on the exchange?
        elif self.sell_orders_on_low_liquidity_exchange < 1 or self.buy_orders_on_low_liquidity_exchange < 1:
            self.cancel_all_orders()
            proposal = self.create_proposal_based_on_high_liquidity_exchange_price()
            adjusted_proposal = self.adjust_proposal_to_budget(proposal)
            self.place_orders(adjusted_proposal)
            # Update timestamp
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

        # Check profitability of order in low liquidity exchange
        for order in self.get_active_orders(connector_name=self.low_liquidity_exchange):
            if order.is_buy:
                high_liquidity_exchange_sell_result = self.high_liquidity_connector().get_price_for_volume(
                    self.trading_pair, False, self.order_amount)
                buy_cancel_threshold = high_liquidity_exchange_sell_result.result_price * Decimal(
                    1 - self.min_spread_bps / 10000)
                if order.price > buy_cancel_threshold:
                    self.cancel_all_orders()
                    proposal = self.create_proposal_based_on_high_liquidity_exchange_price()
                    adjusted_proposal = self.adjust_proposal_to_budget(proposal)
                    self.place_orders(adjusted_proposal)
                    # Update timestamp
                    self.create_timestamp = self.order_refresh_time + self.current_timestamp

            else:
                high_liquidity_exchange_buy_result = self.high_liquidity_connector().get_price_for_volume(
                    self.trading_pair, True, self.order_amount)
                sell_cancel_threshold = high_liquidity_exchange_buy_result.result_price * Decimal(
                    1 + self.min_spread_bps / 10000)
                if order.price < sell_cancel_threshold:
                    self.cancel_all_orders()
                    proposal = self.create_proposal_based_on_high_liquidity_exchange_price()
                    adjusted_proposal = self.adjust_proposal_to_budget(proposal)
                    self.place_orders(adjusted_proposal)
                    # Update timestamp
                    self.create_timestamp = self.order_refresh_time + self.current_timestamp

        # Check balances and notify when balance is low
        list_of_data = self.get_balance_df().to_dict("split")["data"]
        # list of data is a list containing nested list that contain all the elements of 1 row of the dataframe in
        # the following order [exchange, asset, total balance, available balance].
        # To check the available balance we loop through each list and identify the necessary variables.
        for data in list_of_data:
            exchange = data[0]
            asset = data[1]
            available_balance = data[3]

            if asset == self.base_asset:
                if available_balance < self.min_base_asset:
                    message = f"Available balance for {asset} on {exchange} is {available_balance} {asset} and " \
                              f"should be adjusted. "
                    self.notify_hb_app(message)

            elif asset == self.quote_asset:
                if available_balance < self.min_quote_asset:
                    message = f"Available balance for {asset} on {exchange} is {available_balance} {asset} and " \
                              f"should be adjusted. "
                    self.notify_hb_app(message)

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
        self.logger().info("All orders on the low liquidity exchanged are canceled")

    def create_proposal_based_on_high_liquidity_exchange_price(self):
        """Determine best ask and bid price by fetching the necessary data from the hedging exchange (=high liquidity
        exchange), calculate order_amount, then create a buy and sell order-candidate"""
        # Using the logic of xemm example to calculate the buy and sell price on the low liquidity exchange.
        high_liquidity_exchange_buy_result = self.high_liquidity_connector().get_price_for_volume(self.trading_pair,
                                                                                                  True,
                                                                                                  self.order_amount)
        high_liquidity_exchange_sell_result = self.high_liquidity_connector().get_price_for_volume(self.trading_pair,
                                                                                                   False,
                                                                                                   self.order_amount)
        # Determine buy/sell price on low liq ex
        low_liquidity_exchange_buy_price = high_liquidity_exchange_sell_result.result_price * Decimal(
            1 - self.spread_bps / 10000)
        low_liquidity_exchange_sell_price = high_liquidity_exchange_buy_result.result_price * Decimal(
            1 + self.spread_bps / 10000)

        # Determine order amount
        balance_for_buy_order = self.high_liquidity_connector().get_available_balance(self.base_asset)
        # self.logger().info(f"balance for buy order is {balance_for_buy_order}")
        buy_order_amount = min(self.order_amount, balance_for_buy_order)
        # self.logger().info(f"balance for buy order is {buy_order_amount}")
        usdt_balance = self.high_liquidity_connector().get_available_balance(self.quote_asset)
        balance_for_sell_order = usdt_balance / high_liquidity_exchange_buy_result.result_price
        sell_order_amount = min(self.order_amount, balance_for_sell_order)

        buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(buy_order_amount),
                                   price=low_liquidity_exchange_buy_price)
        sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(sell_order_amount),
                                    price=low_liquidity_exchange_sell_price)
        return buy_order, sell_order

    def adjust_proposal_to_budget(self, proposal):
        """Adjust the order-candidate to the available budget"""
        proposal_adjusted = self.connectors[self.low_liquidity_exchange].budget_checker.adjust_candidates(
            proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, adjusted_proposal):
        """For each order in the adjusted proposal (= adjusted order-candidates)-> use method place_order()"""
        for order in adjusted_proposal:
            self.place_order(order=order)

    def place_order(self, order):
        """Places buy and sell orders."""
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=self.low_liquidity_exchange, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
            # Add orders to the variable that keeps track of the number of orders on the exchange:
            self.sell_orders_on_low_liquidity_exchange += 1

        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=self.low_liquidity_exchange, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
            # Add orders to the variable that keeps track of the number of orders on the exchange:
            self.buy_orders_on_low_liquidity_exchange += 1

    # Methods concerning the high liquidity exchange
    def is_active_maker_order(self, event: OrderFilledEvent):
        """
        Helper function that checks if order is an active order on the maker exchange
        """
        for order in self.get_active_orders(connector_name=self.low_liquidity_exchange):
            if order.client_order_id == event.order_id:
                return True
        return False

    def did_fill_order(self, event: OrderFilledEvent):
        # Calculate volatility on high liquidity exchange based on bidask-spread
        best_ask = self.connectors[self.high_liquidity_exchange].get_price(self.trading_pair, is_buy=True)
        best_bid = self.connectors[self.high_liquidity_exchange].get_price(self.trading_pair, is_buy=False)
        bid_ask_spread_bps = (best_ask - best_bid) * 10000
        if bid_ask_spread_bps > 15:  # This can be adjusted
            volatility = "high"
        else:
            volatility = "low"

        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            self.logger().info(f"Buy order filled on low liquidity exchange with price: {event.price}")
            hedge_order_amount = event.amount

            # When buy order filled we place hedge sell order on best_ask price
            best_ask = self.high_liquidity_exchange.get_price(self.trading_pair, is_buy=True)
            if volatility == "high":
                hedge_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True,
                                             order_type=OrderType.LIMIT,
                                             order_side=TradeType.SELL, amount=Decimal(hedge_order_amount),
                                             price=best_ask)
            elif volatility == "low":
                hedge_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=False,
                                             order_type=OrderType.MARKET,
                                             order_side=TradeType.SELL, amount=Decimal(hedge_order_amount),
                                             price=best_ask)
            hedge_adjusted = self.connectors[self.low_liquidity_exchange].budget_checker.adjust_candidates(
                hedge_order,
                all_or_none=True)
            self.sell(connector_name=self.high_liquidity_exchange,
                      trading_pair=self.trading_pair,
                      amount=hedge_adjusted.amount,
                      order_type=hedge_adjusted.order_type,
                      price=hedge_adjusted.price)

        if event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
            self.logger().info(f"Sell order filled on low liquidity exchange with price: {event.price}")
            hedge_order_amount = event.amount

            # When sell order filled we place hedge buy order on best_bid price
            best_bid = self.high_liquidity_exchange.get_price(self.trading_pair, is_buy=True)
            if volatility == "high":
                hedge_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True,
                                             order_type=OrderType.LIMIT,
                                             order_side=TradeType.BUY, amount=Decimal(hedge_order_amount),
                                             price=best_bid)
            elif volatility == "low":
                hedge_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=False,
                                             order_type=OrderType.MARKET,
                                             order_side=TradeType.BUY, amount=Decimal(hedge_order_amount),
                                             price=best_bid)
            hedge_adjusted = self.connectors[self.low_liquidity_exchange].budget_checker.adjust_candidates(
                hedge_order,
                all_or_none=True)
            self.buy(connector_name=self.high_liquidity_exchange,
                     trading_pair=self.trading_pair,
                     amount=hedge_adjusted.amount,
                     order_type=hedge_adjusted.order_type,
                     price=hedge_adjusted.price)

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
