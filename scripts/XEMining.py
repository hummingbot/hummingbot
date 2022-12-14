from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class XEMining(ScriptStrategyBase):

    maker_exchange = "kucoin_paper_trade"
    maker_pair = "FRONT-USDT"
    taker_exchange = "gate_io_paper_trade"
    taker_pair = "FRONT-USDT"

    order_amount = 250                  # amount for each order
    spread_bps = 4                    # bot places maker orders at this spread to taker price
    min_spread_bps = 0                  # bot refreshes order if spread is lower than min-spread
    slippage_buffer_spread_bps = 100    # buffer applied to limit taker hedging trades on taker exchange
    max_order_age = 120                 # bot refreshes orders after this age

    markets = {maker_exchange: {maker_pair}, taker_exchange: {taker_pair}}

    buy_order_placed = False
    sell_order_placed = False

    create_timestamp = 0
    price_timestamp = 0

    last_midprices = []

    def on_tick(self):

        base_path = Path(__file__).parent
        file_path = (base_path / "../data/trades_XEMi.csv").resolve()
        # with open(file_path) as f:
        #     test = [line for line in csv.reader(f)]
        #     self.logger().info(f"Test: {test}")

        # read csv file
        df = pd.read_csv(file_path)
        self.logger().info(f"Dataframe: {df}")

        if self.price_timestamp <= self.current_timestamp:
            orderBook = self.connectors[self.maker_exchange].get_order_book(self.maker_pair)
            # print snapshot of orderBook
            self.logger().info(f"OrderBook: {orderBook}")
            # ask_entries
            ask_entries = orderBook.ask_entries()
            askVol = 0
            askPriceTimesVol = 0
            for entry in ask_entries:
                # self.logger().info(f"Ask Entry: {entry}")
                # self.logger().info(f"Ask Entry price: {entry.price}")
                # self.logger().info(f"Ask Entry amount: {entry.amount}")
                askVol += entry.amount
                askPriceTimesVol += entry.price * entry.amount

            # bid_entries
            bid_entries = orderBook.bid_entries()
            bidVol = 0
            bidPriceTimesVol = 0
            for entry in bid_entries:
                # self.logger().info(f"Bid Entry: {entry}")
                # self.logger().info(f"Bid Entry price: {entry.price}")
                # self.logger().info(f"Bid Entry amount: {entry.amount}")
                bidVol += entry.amount
                bidPriceTimesVol += entry.price * entry.amount

            # calculate midprice
            p = (askPriceTimesVol + bidPriceTimesVol) / (askVol + bidVol)
            self.last_midprices.append(p)

            # loop through midprices to get midprice
            for i in range(0, len(self.last_midprices)):
                self.logger().info(f"Midprice: {self.last_midprices[i]} for {self.maker_pair} on {self.maker_exchange}")

            volatility = np.std(self.last_midprices)
            annualized_vol = volatility * 60 * 24 * 365
            self.logger().info(f"Volatility: {volatility}")
            self.logger().info(f"Annualized Volatility: {annualized_vol}")

            # adjust spread_bps based on volatility by multiplying spread_bps by volatility
            if annualized_vol > 5 and annualized_vol < 10:
                self.spread_bps = 4
            elif annualized_vol >= 10:
                self.spread_bps = 5
            else:
                self.spread_bps = 3

            self.logger().info(f"Adjusted spread_bps: {self.spread_bps}")
            self.price_timestamp = self.current_timestamp + 60
            # vwap = self.connectors[self.maker_exchange].get_vwap_for_volume(self.maker_pair, is_buy=True, volume = 10)
            # result_price = vwap.result_price
            # result_volume = vwap.result_volume
            # self.logger().info(f"VWAP: {result_price} for {result_volume} {self.maker_pair}")

        # Calculate volatility of last 30 midprices
        if len(self.last_midprices) >= 30:
            self.last_midprices.pop(0)

        # self.logger().info(f"create timestamp {self.create_timestamp}")
        # self.logger().info(f"current timestamp {self.current_timestamp}")
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True, self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False, self.order_amount)

        if not self.buy_order_placed:
            maker_buy_price = taker_sell_result.result_price * Decimal(1 - self.spread_bps / 10000)
            buy_order_amount = min(self.order_amount, self.buy_hedging_budget())
            buy_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(buy_order_amount), price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=False)
            self.buy(self.maker_exchange, self.maker_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
            self.buy_order_placed = True

        if not self.sell_order_placed:
            maker_sell_price = taker_buy_result.result_price * Decimal(1 + self.spread_bps / 10000)
            sell_order_amount = min(self.order_amount, self.sell_hedging_budget())
            sell_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=Decimal(sell_order_amount), price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=False)
            self.sell(self.maker_exchange, self.maker_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.sell_order_placed = True

        for order in self.get_active_orders(connector_name=self.maker_exchange):
            cancel_timestamp = order.creation_timestamp / 1000000 + self.max_order_age
            if order.is_buy:
                buy_cancel_threshold = taker_sell_result.result_price * Decimal(1 - self.min_spread_bps / 10000)
                if order.price > buy_cancel_threshold or cancel_timestamp < self.current_timestamp:
                    self.logger().info(f"Cancelling buy order: {order.client_order_id}")
                    self.cancel(self.maker_exchange, order.trading_pair, order.client_order_id)
                    self.buy_order_placed = False
            else:
                sell_cancel_threshold = taker_buy_result.result_price * Decimal(1 + self.min_spread_bps / 10000)
                if order.price < sell_cancel_threshold or cancel_timestamp < self.current_timestamp:
                    self.logger().info(f"Cancelling sell order: {order.client_order_id}")
                    self.cancel(self.maker_exchange, order.trading_pair, order.client_order_id)
                    self.sell_order_placed = False
        return

    def buy_hedging_budget(self) -> Decimal:
        balance = self.connectors[self.taker_exchange].get_available_balance("ETH")
        return balance

    def sell_hedging_budget(self) -> Decimal:
        balance = self.connectors[self.taker_exchange].get_available_balance("USDT")
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True, self.order_amount)
        return balance / taker_buy_result.result_price

    def is_active_maker_order(self, event: OrderFilledEvent):
        """
        Helper function that checks if order is an active order on the maker exchange
        """
        for order in self.get_active_orders(connector_name=self.maker_exchange):
            if order.client_order_id == event.order_id:
                return True
        return False

    def did_fill_order(self, event: OrderFilledEvent):

        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False, self.order_amount)
            sell_price_with_slippage = taker_sell_result.result_price * Decimal(1 - self.slippage_buffer_spread_bps / 10000)
            self.logger().info(f"Filled maker buy order with price: {event.price}")
            sell_spread_bps = (taker_sell_result.result_price - event.price) / mid_price * 10000
            self.logger().info(f"Sending taker sell order at price: {taker_sell_result.result_price} spread: {int(sell_spread_bps)} bps")
            sell_order = OrderCandidate(trading_pair=self.taker_pair, is_maker=False, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=Decimal(event.amount), price=sell_price_with_slippage)
            sell_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=False)
            self.sell(self.taker_exchange, self.taker_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.buy_order_placed = False
        else:
            if event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
                taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True, self.order_amount)
                buy_price_with_slippage = taker_buy_result.result_price * Decimal(1 + self.slippage_buffer_spread_bps / 10000)
                buy_spread_bps = (event.price - taker_buy_result.result_price) / mid_price * 10000
                self.logger().info(f"Filled maker sell order at price: {event.price}")
                self.logger().info(f"Sending taker buy order: {taker_buy_result.result_price} spread: {int(buy_spread_bps)}")
                buy_order = OrderCandidate(trading_pair=self.taker_pair, is_maker=False, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(event.amount), price=buy_price_with_slippage)
                buy_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=False)
                self.buy(self.taker_exchange, self.taker_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
                self.sell_order_placed = False

    def exchanges_df(self) -> pd.DataFrame:
        """
        Return a custom data frame of prices on maker vs taker exchanges for display purposes
        """
        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        maker_buy_result = self.connectors[self.maker_exchange].get_price_for_volume(self.taker_pair, True, self.order_amount)
        maker_sell_result = self.connectors[self.maker_exchange].get_price_for_volume(self.taker_pair, False, self.order_amount)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True, self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False, self.order_amount)
        maker_buy_spread_bps = (maker_buy_result.result_price - taker_buy_result.result_price) / mid_price * 10000
        maker_sell_spread_bps = (taker_sell_result.result_price - maker_sell_result.result_price) / mid_price * 10000
        columns = ["Exchange", "Market", "Mid Price", "Buy Price", "Sell Price", "Buy Spread", "Sell Spread"]
        data = []
        data.append([
            self.maker_exchange,
            self.maker_pair,
            float(self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)),
            float(maker_buy_result.result_price),
            float(maker_sell_result.result_price),
            int(maker_buy_spread_bps),
            int(maker_sell_spread_bps)
        ])
        data.append([
            self.taker_exchange,
            self.taker_pair,
            float(self.connectors[self.taker_exchange].get_mid_price(self.maker_pair)),
            float(taker_buy_result.result_price),
            float(taker_sell_result.result_price),
            int(-maker_buy_spread_bps),
            int(-maker_sell_spread_bps)
        ])
        df = pd.DataFrame(data=data, columns=columns)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        """
        Returns a custom data frame of all active maker orders for display purposes
        """
        columns = ["Exchange", "Market", "Side", "Price", "Amount", "Spread Mid", "Spread Cancel", "Age"]
        data = []
        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True, self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False, self.order_amount)
        buy_cancel_threshold = taker_sell_result.result_price * Decimal(1 - self.min_spread_bps / 10000)
        sell_cancel_threshold = taker_buy_result.result_price * Decimal(1 + self.min_spread_bps / 10000)
        for connector_name, connector in self.connectors.items():
            for order in self.get_active_orders(connector_name):
                age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
                spread_mid_bps = (mid_price - order.price) / mid_price * 10000 if order.is_buy else (order.price - mid_price) / mid_price * 10000
                spread_cancel_bps = (buy_cancel_threshold - order.price) / buy_cancel_threshold * 10000 if order.is_buy else (order.price - sell_cancel_threshold) / sell_cancel_threshold * 10000
                data.append([
                    self.maker_exchange,
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
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        exchanges_df = self.exchanges_df()
        lines.extend(["", "  Exchanges:"] + ["    " + line for line in exchanges_df.to_string(index=False).split("\n")])

        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        # orderBook = self.connectors[self.maker_exchange].get_order_book(self.maker_pair)
        # lines.extend(["", "  Order Book:"] + ["    " + line for line in orderBook.to_string().split("\n")])

        return "\n".join(lines)
