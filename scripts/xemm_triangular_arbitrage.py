from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.connector.exchange_base import ExchangeBase

class XEMMTriangularArbitrage(ScriptStrategyBase):

    maker_exchange = "kucoin"
    maker_pair = "ELF-BTC"
    taker_exchange = "binance"
    taker_pair1 = "ELF-USDT"
    taker_pair2 = "BTC-USDT"

    order_amount = Decimal(40)         # amount for each order
    spread_bps = 10                     # bot places maker orders at this spread to taker price
    min_spread_bps = 0                  # bot refreshes order if spread is lower than min-spread
    slippage_buffer_spread_bps = 100    # buffer applied to limit taker hedging trades on taker exchange
    max_order_age = 8                   # bot refreshes orders after this age
    min_profitability = 0.0045

    markets = {maker_exchange: {maker_pair}, taker_exchange: {taker_pair1, taker_pair2}}

    buy_order_placed = False
    sell_order_placed = False

    maker_pair_base_asset, maker_pair_quote_asset = maker_pair.split("-")
    taker_pair1_base_asset, taker_pair1_quote_asset = taker_pair1.split("-")
    taker_pair2_base_asset, taker_pair2_quote_asset = taker_pair2.split("-")
    def on_tick(self):
        taker = MarketTradingPairTuple(self.connectors[self.taker_exchange], self.taker_pair1, self.taker_pair1_base_asset, self.taker_pair1_quote_asset)
        third = MarketTradingPairTuple(self.connectors[self.taker_exchange], self.taker_pair2, self.taker_pair2_base_asset, self.taker_pair2_quote_asset)

        conversion_price_bid = third.get_vwap_for_volume(volume=self.order_amount * taker.get_mid_price(), is_buy=True).result_price
        effective_hedging_price_uncoverted_bid = taker.get_vwap_for_volume(volume=self.order_amount, is_buy=False).result_price
        effective_hedging_price_converted_bid = effective_hedging_price_uncoverted_bid / conversion_price_bid
        maker_bid_order_price = effective_hedging_price_converted_bid / Decimal(1.004)

        conversion_price_ask = third.get_vwap_for_volume(volume=self.order_amount * taker.get_mid_price(),is_buy=True).result_price
        effective_hedging_price_uncoverted_ask = taker.get_vwap_for_volume(volume=self.order_amount,is_buy=False).result_price
        effective_hedging_price_converted_ask = effective_hedging_price_uncoverted_ask / conversion_price_ask
        maker_ask_order_price = effective_hedging_price_converted_ask * Decimal(1.004)

        if not self.buy_order_placed:
            maker_buy_price = maker_bid_order_price
            buy_order_amount = self.order_amount
            buy_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(buy_order_amount), price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=False)
            self.buy(self.maker_exchange, self.maker_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
            self.buy_order_placed = True

        if not self.sell_order_placed:
            maker_sell_price = maker_ask_order_price
            sell_order_amount = self.order_amount
            sell_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=Decimal(sell_order_amount), price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=False)
            self.sell(self.maker_exchange, self.maker_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.sell_order_placed = True

        for order in self.get_active_orders(connector_name=self.maker_exchange):
            cancel_timestamp = order.creation_timestamp / 1000000 + self.max_order_age
            if order.is_buy:
                if cancel_timestamp < self.current_timestamp:
                    self.logger().info(f"Cancelling buy order: {order.client_order_id}")
                    self.cancel(self.maker_exchange, order.trading_pair, order.client_order_id)
                    self.buy_order_placed = False
            else:
                if cancel_timestamp < self.current_timestamp:
                    self.logger().info(f"Cancelling sell order: {order.client_order_id}")
                    self.cancel(self.maker_exchange, order.trading_pair, order.client_order_id)
                    self.sell_order_placed = False
        return

    def buy_hedging_budget(self) -> Decimal:
        balance = self.connectors[self.taker_exchange].get_available_balance("QTUM")
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

    def get_base_amount_for_quote_volume(self, orderbook_entries, quote_volume) -> Decimal:
        """
        Calculates base amount that you get for the quote volume using the orderbook entries
        """
        cumulative_volume = 0.
        cumulative_base_amount = 0.
        quote_volume = float(quote_volume)

        for order_book_row in orderbook_entries:
            row_amount = order_book_row.amount
            row_price = order_book_row.price
            row_volume = row_amount * row_price
            if row_volume + cumulative_volume >= quote_volume:
                row_volume = quote_volume - cumulative_volume
                row_amount = row_volume / row_price
            cumulative_volume += row_volume
            cumulative_base_amount += row_amount
            if cumulative_volume >= quote_volume:
                break
        return Decimal(cumulative_base_amount)

    def did_fill_order(self, event: OrderFilledEvent):

        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            taker1_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair1, False, self.order_amount)
            taker1_sell_amount = event.amount
            taker2_buy_amount = self.connectors[self.taker_exchange].get_quote_volume_for_base_amount(self.taker_pair1, 1, taker1_sell_amount).result_volume
            taker2_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair2, False, taker2_buy_amount)
            taker2_order_book = self.connectors[self.taker_exchange].get_order_book(self.taker_pair2)
            taker2_final_amount = self.get_base_amount_for_quote_volume(taker2_order_book.ask_entries(), taker2_buy_amount)

            sell_price_with_slippage = taker1_sell_result.result_price * Decimal(1 - self.slippage_buffer_spread_bps / 10000)
            self.logger().info(f"Filled maker buy order with price: {event.price}")
            self.logger().info(f"Sending taker sell order at price: {taker1_sell_result.result_price} ")
            sell_order = OrderCandidate(trading_pair=self.taker_pair1, is_maker=False, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=Decimal(taker1_sell_amount), price=sell_price_with_slippage)
            sell_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=False)
            self.logger().info(f"sell_order_adjusted.amount: {sell_order_adjusted.amount} ")
            self.sell(self.taker_exchange, self.taker_pair1, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)


            buy_price_with_slippage = taker2_buy_result.result_price * Decimal(1 + self.slippage_buffer_spread_bps / 10000)
            self.logger().info(f"Sending taker buy order at price: {taker2_buy_result.result_price} ")
            buy_order = OrderCandidate(trading_pair=self.taker_pair2, is_maker=False, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(taker2_final_amount), price=buy_price_with_slippage)
            buy_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=False)
            self.logger().info(f"buy_order_adjusted.amount: {buy_order_adjusted.amount} ")
            self.buy(self.taker_exchange, self.taker_pair2, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
            self.buy_order_placed = False

        else:
            if event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
                taker1_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair1, True, self.order_amount)
                taker1_buy_amount = self.event.amount
                taker2_sell_amount = self.connectors[self.taker_exchange].get_quote_volume_for_base_amount(self.taker_pair1, 0, taker1_buy_amount).result_volume
                taker2_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair2, False, taker2_sell_amount)
                taker2_order_book = self.connectors[self.taker_exchange].get_order_book(self.taker_pair2)
                taker2_final_amount = self.get_base_amount_for_quote_volume(taker2_order_book.bid_entries(), taker2_sell_amount)

                buy_price_with_slippage = taker1_buy_result.result_price * Decimal(1 + self.slippage_buffer_spread_bps / 10000)
                self.logger().info(f"Filled maker sell order with price: {event.price}")
                self.logger().info(f"Sending taker buy order at price: {taker1_buy_result.result_price} ")
                buy_order = OrderCandidate(trading_pair=self.taker_pair1, is_maker=False, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(taker1_buy_amount), price=buy_price_with_slippage)
                buy_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(buy_order, all_or_none=False)
                self.logger().info(f"buy_order_adjusted.amount: {buy_order_adjusted.amount} ")
                self.buy(self.taker_exchange, self.taker_pair1, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)

                sell_price_with_slippage = taker2_sell_result.result_price * Decimal(1 - self.slippage_buffer_spread_bps / 10000)
                self.logger().info(f"Sending taker sell order at price: {taker2_sell_result.result_price} ")
                sell_order = OrderCandidate(trading_pair=self.taker_pair2, is_maker=False, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=Decimal(taker2_final_amount), price=sell_price_with_slippage)
                sell_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(sell_order, all_or_none=False)
                self.logger().info(f"sell_order_adjusted.amount: {sell_order_adjusted.amount} ")
                self.sell(self.taker_exchange, self.taker_pair2, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
                self.sell_order_placed = False


    def exchanges_df(self) -> pd.DataFrame:
            """
            Return a custom data frame of prices on maker vs taker exchanges for display purposes
            """
            columns = ["Exchange", "Market", "Mid Price", "Best Bid", "Best Offer"]
            data = []
            data.append([
                self.maker_exchange,
                self.maker_pair,
                float(self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)),
                float(self.connectors[self.maker_exchange].get_price(self.maker_pair, True)),
                float(self.connectors[self.maker_exchange].get_price(self.maker_pair, False)),
            ])
            data.append([
                self.taker_exchange,
                self.taker_pair1,
                float(self.connectors[self.taker_exchange].get_mid_price(self.taker_pair1)),
                float(self.connectors[self.taker_exchange].get_price(self.taker_pair1, True)),
                float(self.connectors[self.taker_exchange].get_price(self.taker_pair1, False)),
            ])
            data.append([
                self.taker_exchange,
                self.taker_pair2,
                float(self.connectors[self.taker_exchange].get_mid_price(self.taker_pair2)),
                float(self.connectors[self.taker_exchange].get_price(self.taker_pair2, True)),
                float(self.connectors[self.taker_exchange].get_price(self.taker_pair2, False)),
            ])

            df = pd.DataFrame(data=data, columns=columns)
            return df

    def active_orders_df(self) -> pd.DataFrame:
        """
        Returns a custom data frame of all active maker orders for display purposes
        """
        columns = ["Exchange", "Market", "Side", "Price", "Amount", "Age"]
        data = []
        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair1, True, self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair1, False, self.order_amount)
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

        return "\n".join(lines)
