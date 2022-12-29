from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_book_query_result import ClientOrderBookQueryResult
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class XEMMPerpetualHedge(ScriptStrategyBase):
    """
    BotCamp Cohort: Nov 2022
    Design Template: https://www.notion.so/Market-neutral-XEMM-by-hedging-f3cee9c442154fa28703c66e3ed107f9
    Description: A variation of the cross-exchange market making strategy that hedges total base inventory held
    on the maker and taker exchanges with a perpetual short position.
    """

    maker_exchange = "kucoin_paper_trade"
    maker_pair = "ETH-USDT"
    taker_exchange = "binance_paper_trade"
    taker_pair = "ETH-USDT"
    perpetual_exchange = "binance_perpetual_testnet"
    perpetual_pair = "ETH-USDT"

    order_amount = 0.1                  # amount for each order
    spread_bps = 10                     # bot places maker orders at this spread to taker price
    min_spread_bps = 5                  # bot refreshes order if spread is lower than min-spread
    slippage_buffer_spread_bps = 100    # buffer applied to limit taker hedging trades on taker exchange
    max_order_age = 120                 # bot refreshes orders after this age

    markets = {maker_exchange: {maker_pair}, taker_exchange: {taker_pair}, perpetual_exchange: {perpetual_pair}}

    initialized = False

    buy_order_placed = False
    sell_order_placed = False

    taker_order_id = ''

    def on_tick(self):
        if not self.initialized:
            self.logger().info('Initializing hedge position')
            self.adjust_perpetual_hedge_if_required()
            self.initialized = True

        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        self.place_buy_order_if_none(taker_sell_result)
        self.place_sell_order_if_none(taker_buy_result)
        self.cancel_orders_if_invalidated(taker_buy_result, taker_sell_result)

    def did_fill_order(self, event: OrderFilledEvent):
        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            self.place_taker_sell_order(event)
        elif event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
            self.place_taker_buy_order(event)
        elif event.order_id == self.taker_order_id:
            self.adjust_perpetual_hedge_if_required()
            self.taker_order_id = ''

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
            lines.extend(
                ["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        lines.extend(["", f"  Hedge Discrepancy (base asset): {self._calculate_perpetual_discrepancy()}"])

        return "\n".join(lines)

    def place_buy_order_if_none(self, taker_sell_result: ClientOrderBookQueryResult):
        if not self.buy_order_placed:
            maker_buy_price = taker_sell_result.result_price * Decimal(1 - self.spread_bps / 10000)
            buy_order_amount = min(self.order_amount, self.get_taker_buy_budget())
            buy_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT,
                                       order_side=TradeType.BUY, amount=Decimal(buy_order_amount),
                                       price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(buy_order,
                                                                                                      all_or_none=False)
            self.buy(self.maker_exchange, self.maker_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type,
                     buy_order_adjusted.price)
            self.buy_order_placed = True

    def place_sell_order_if_none(self, taker_buy_result: ClientOrderBookQueryResult):
        if not self.sell_order_placed:
            maker_sell_price = taker_buy_result.result_price * Decimal(1 + self.spread_bps / 10000)
            sell_order_amount = min(self.order_amount, self.get_taker_sell_budget())
            sell_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=TradeType.SELL, amount=Decimal(sell_order_amount),
                                        price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(sell_order,
                                                                                                       all_or_none=False
                                                                                                       )
            self.sell(self.maker_exchange, self.maker_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type,
                      sell_order_adjusted.price)
            self.sell_order_placed = True

    def cancel_orders_if_invalidated(
        self, taker_buy_result: ClientOrderBookQueryResult, taker_sell_result: ClientOrderBookQueryResult
    ):
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

    def get_taker_buy_budget(self) -> float:
        balance = self.connectors[self.taker_exchange].get_available_balance(self.taker_pair.split('-')[0])
        return float(balance)

    def get_taker_sell_budget(self) -> float:
        balance = self.connectors[self.taker_exchange].get_available_balance(self.taker_pair.split('-')[1])
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(
            self.taker_pair, True, self.order_amount)
        return float(balance / taker_buy_result.result_price)

    def is_active_maker_order(self, event: OrderFilledEvent):
        """
        Helper function that checks if order is an active order on the maker exchange
        """
        return event.order_id in [
            order.client_order_id for order in self.get_active_orders(connector_name=self.maker_exchange)
        ]

    def place_taker_buy_order(self, event: OrderFilledEvent):
        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        buy_price_with_slippage = taker_buy_result.result_price * Decimal(1 + self.slippage_buffer_spread_bps / 10000)
        buy_spread_bps = (event.price - taker_buy_result.result_price) / mid_price * 10000
        self.logger().info(f"Filled maker sell order at price: {event.price}")
        self.logger().info(f"Sending taker buy order: {taker_buy_result.result_price} spread: {int(buy_spread_bps)}")
        buy_order = OrderCandidate(trading_pair=self.taker_pair, is_maker=False, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(event.amount),
                                   price=buy_price_with_slippage)
        buy_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(buy_order,
                                                                                                  all_or_none=False)
        self.taker_order_id = self.buy(self.taker_exchange, self.taker_pair, buy_order_adjusted.amount,
                                       buy_order_adjusted.order_type, buy_order_adjusted.price)
        self.sell_order_placed = False

    def place_taker_sell_order(self, event: OrderFilledEvent):
        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        sell_price_with_slippage = taker_sell_result.result_price * Decimal(1 - self.slippage_buffer_spread_bps / 10000)
        self.logger().info(f"Filled maker buy order with price: {event.price}")
        sell_spread_bps = (taker_sell_result.result_price - event.price) / mid_price * 10000
        self.logger().info(
            f"Sending taker sell order at price: {taker_sell_result.result_price} spread: {int(sell_spread_bps)} bps")
        sell_order = OrderCandidate(trading_pair=self.taker_pair, is_maker=False, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(event.amount),
                                    price=sell_price_with_slippage)
        sell_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(sell_order,
                                                                                                   all_or_none=False)
        self.taker_order_id = self.sell(self.taker_exchange, self.taker_pair, sell_order_adjusted.amount,
                                        sell_order_adjusted.order_type, sell_order_adjusted.price)
        self.buy_order_placed = False

    def adjust_perpetual_hedge_if_required(self):
        perpetual_discrepancy = self._calculate_perpetual_discrepancy()
        minimum_amount = self.connectors[self.perpetual_exchange].get_order_size_quantum(self.perpetual_pair, 0)
        if perpetual_discrepancy > minimum_amount:
            self._increase_perpetual_hedge_if_required(perpetual_discrepancy)
        elif perpetual_discrepancy < -minimum_amount:
            self._decrease_perpetual_hedge_if_required(perpetual_discrepancy)

    def _calculate_perpetual_discrepancy(self) -> Decimal:
        base_asset = self.taker_pair.split('-')[0]
        maker_base_balance = self.connectors[self.maker_exchange].get_balance(base_asset)
        taker_base_balance = self.connectors[self.taker_exchange].get_balance(base_asset)
        total_base_balance = maker_base_balance + taker_base_balance
        open_positions = self.connectors[self.perpetual_exchange].account_positions
        perpetual_pair = self.perpetual_pair.replace('-', '')
        open_position_amount = 0
        if open_positions.get(perpetual_pair):
            open_position = open_positions[perpetual_pair]
            open_position_amount = open_position._amount
        return total_base_balance + open_position_amount

    def _increase_perpetual_hedge_if_required(self, perpetual_discrepancy: Decimal):
        perpetual_sell_result = self.connectors[self.perpetual_exchange].get_price_for_volume(self.perpetual_pair,
                                                                                              False, self.order_amount)
        sell_price_with_slippage = perpetual_sell_result.result_price * Decimal(
            1 + self.slippage_buffer_spread_bps / 10000)
        sell_order = OrderCandidate(trading_pair=self.perpetual_pair, is_maker=False, order_type=OrderType.MARKET,
                                    order_side=TradeType.BUY, amount=abs(perpetual_discrepancy),
                                    price=sell_price_with_slippage)
        sell_order_adjusted = self.connectors[self.perpetual_exchange].budget_checker.adjust_candidate(
            sell_order, all_or_none=False)
        self.logger().info(f'Increasing hedge position by {abs(perpetual_discrepancy)}')
        self.sell(self.perpetual_exchange, self.perpetual_pair, sell_order_adjusted.amount,
                  sell_order_adjusted.order_type, sell_order_adjusted.price)

    def _decrease_perpetual_hedge_if_required(self, perpetual_discrepancy: Decimal):
        perpetual_buy_result = self.connectors[self.perpetual_exchange].get_price_for_volume(self.perpetual_pair, True,
                                                                                             self.order_amount)
        buy_price_with_slippage = perpetual_buy_result.result_price * Decimal(
            1 + self.slippage_buffer_spread_bps / 10000)
        buy_order = OrderCandidate(trading_pair=self.perpetual_pair, is_maker=False, order_type=OrderType.MARKET,
                                   order_side=TradeType.BUY, amount=abs(perpetual_discrepancy),
                                   price=buy_price_with_slippage)
        buy_order_adjusted = self.connectors[self.perpetual_exchange].budget_checker.adjust_candidate(buy_order,
                                                                                                      all_or_none=False)
        self.logger().info(f'Decreasing hedge position by {abs(perpetual_discrepancy)}')
        self.buy(self.perpetual_exchange, self.perpetual_pair, buy_order_adjusted.amount,
                 buy_order_adjusted.order_type, buy_order_adjusted.price)

    def exchanges_df(self) -> pd.DataFrame:
        """
        Return a custom data frame of prices on maker vs taker exchanges for display purposes
        """
        mid_price = self.connectors[self.maker_exchange].get_mid_price(self.maker_pair)
        maker_buy_result = self.connectors[self.maker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        maker_sell_result = self.connectors[self.maker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
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
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        buy_cancel_threshold = taker_sell_result.result_price * Decimal(1 - self.min_spread_bps / 10000)
        sell_cancel_threshold = taker_buy_result.result_price * Decimal(1 + self.min_spread_bps / 10000)
        for connector_name, connector in self.connectors.items():
            for order in self.get_active_orders(connector_name):
                age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
                spread_mid_bps = (mid_price - order.price) / mid_price * 10000\
                    if order.is_buy else (order.price - mid_price) / mid_price * 10000
                spread_cancel_bps = (buy_cancel_threshold - order.price) / buy_cancel_threshold * 10000\
                    if order.is_buy else (order.price - sell_cancel_threshold) / sell_cancel_threshold * 10000
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
