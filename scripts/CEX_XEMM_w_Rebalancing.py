from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType, PriceType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CEX_XEMM_w_Rebalancing(ScriptStrategyBase):

    maker_exchange = "kucoin_paper_trade"
    taker_exchange = "binance_paper_trade"

    maker_base = "AVAX"
    maker_quote = "USDT"
    taker_base = "AVAX"
    taker_quote = "USDT"

    price_source = PriceType.LastTrade
    slippage_buffer_spread_bps = 5
    maker_pair = f"{maker_base}-{maker_quote}"
    taker_pair = f"{taker_base}-{taker_quote}"
    target_base_asset_percentage = 0.3
    rebalancing_pct = 0.2

    markets = {maker_exchange: {maker_pair}, taker_exchange: {taker_pair}}

    order_amount: int = 20
    exp_profit_bps: int = 20
    min_spread_bps: int = 5
    fee_bps: int = 20

    max_order_age = 120

    buy_order_placed = False
    sell_order_placed = False

    def on_tick(self):
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)

        if not self.buy_order_placed:
            maker_buy_price = taker_sell_result.result_price * Decimal(1 - self.exp_profit_bps / 10000
                                                                       - self.fee_bps / 10000)
            buy_order_amount = min(self.order_amount, self.buy_hedging_budget())
            buy_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT,
                                       order_side=TradeType.BUY, amount=Decimal(buy_order_amount),
                                       price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(buy_order,
                                                                                                      all_or_none=False)
            self.buy(self.maker_exchange, self.maker_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type,
                     buy_order_adjusted.price)
            self.buy_order_placed = True

        if not self.sell_order_placed:
            maker_sell_price = taker_buy_result.result_price * Decimal(1 + self.exp_profit_bps / 10000
                                                                       + self.fee_bps / 10000)
            sell_order_amount = min(self.order_amount, self.sell_hedging_budget())
            sell_order = OrderCandidate(trading_pair=self.maker_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=TradeType.SELL, amount=Decimal(sell_order_amount),
                                        price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.maker_exchange].budget_checker.adjust_candidate(sell_order,
                                                                                                       all_or_none=False)
            self.sell(self.maker_exchange, self.maker_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type,
                      sell_order_adjusted.price)
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
        self.rebalancing()

    def buy_hedging_budget(self) -> Decimal:
        balance = self.connectors[self.taker_exchange].get_available_balance(self.taker_base)
        return balance

    def sell_hedging_budget(self) -> Decimal:
        balance = self.connectors[self.taker_exchange].get_available_balance(self.taker_quote)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        return balance / taker_buy_result.result_price

    def is_active_maker_order(self, event: OrderFilledEvent):
        for order in self.get_active_orders(connector_name=self.maker_exchange):
            if order.client_order_id == event.order_id:
                return True
        return False

    @property
    def maker_connector(self):
        maker_connector = self.connectors[self.maker_exchange]
        return maker_connector

    def base_asset_maker_pct(self):
        base_asset_maker_exchange = self.maker_connector.get_balance(self.maker_base)
        total_balance_maker = base_asset_maker_exchange + \
                              (self.maker_connector.get_balance(self.maker_quote) *
                               self.connectors[self.maker_exchange].get_price_for_volume(self.maker_pair, True,
                                                                                         self.order_amount))
        base_asset_maker_pct = base_asset_maker_exchange / total_balance_maker
        return base_asset_maker_pct

    @property
    def taker_connector(self):
        taker_connector = self.connectors[self.taker_exchange]
        return taker_connector

    def rebalancing(self):
        total_balance_taker = self.taker_connector.get_balance(self.taker_base) + \
                              (self.taker_connector.get_balance(self.taker_quote) *
                               self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                         self.order_amount))
        if self.base_asset_maker_pct() < self.target_base_asset_percentage:
            self.buy(self.maker_connector, self.maker_pair, (self.total_balance_maker * self.rebalancing_pct),
                     order_type=OrderType.MARKET,
                     price=self.connectors[self.maker_exchange].get_price_for_volume(self.maker_pair, True,
                                                                                     self.order_amount).result_price)
            self.sell(self.taker_connector, self.taker_pair, (total_balance_taker * self.rebalancing_pct),
                      order_type=OrderType.MARKET,
                      price=self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                      self.order_amount).result_price)

        if self.base_asset_maker_pct() > self.target_base_asset_percentage:
            self.sell(self.maker_connector, self.maker_pair, (self.total_balance_maker * self.rebalancing_pct),
                      order_type=OrderType.MARKET,
                      price=self.connectors[self.maker_exchange].get_price_for_volume(self.maker_pair, True,
                                                                                      self.order_amount).result_price)
            self.buy(self.taker_connector, self.taker_pair, (total_balance_taker * self.rebalancing_pct),
                     order_type=OrderType.MARKET,
                     price=self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount).result_price)

    def did_fill_order(self, event: OrderFilledEvent):

        last_price = self.connectors[self.maker_exchange].get_price_by_type(self.maker_pair, self.price_source)
        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                          self.order_amount)
            sell_price_with_slippage = taker_sell_result.result_price * Decimal(
                1 - self.slippage_buffer_spread_bps / 10000)
            self.logger().info(f"Filled maker buy order with price: {event.price}")
            sell_spread_bps = (taker_sell_result.result_price - event.price) / last_price * 10000
            self.logger().info(
                f"Sending taker sell order at price: {taker_sell_result.result_price} spread: {int(sell_spread_bps)} bps")
            sell_order = OrderCandidate(trading_pair=self.taker_pair, is_maker=False, order_type=OrderType.LIMIT,
                                        order_side=TradeType.SELL, amount=Decimal(event.amount),
                                        price=sell_price_with_slippage)
            sell_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(sell_order,
                                                                                                       all_or_none=False)
            self.sell(self.taker_exchange, self.taker_pair, sell_order_adjusted.amount,
                      sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.buy_order_placed = False
        else:
            if event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
                taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                             self.order_amount)
                buy_price_with_slippage = taker_buy_result.result_price * Decimal(
                    1 + self.slippage_buffer_spread_bps / 10000)
                buy_spread_bps = (event.price - taker_buy_result.result_price) / last_price * 10000
                self.logger().info(f"Filled maker sell order at price: {event.price}")
                self.logger().info(
                    f"Sending taker buy order: {taker_buy_result.result_price} spread: {int(buy_spread_bps)}")
                buy_order = OrderCandidate(trading_pair=self.taker_pair, is_maker=False, order_type=OrderType.LIMIT,
                                           order_side=TradeType.BUY, amount=Decimal(event.amount),
                                           price=buy_price_with_slippage)
                buy_order_adjusted = self.connectors[self.taker_exchange].budget_checker.adjust_candidate(buy_order,
                                                                                                          all_or_none=False)
                self.buy(self.taker_exchange, self.taker_pair, buy_order_adjusted.amount,
                         buy_order_adjusted.order_type, buy_order_adjusted.price)
                self.sell_order_placed = False

    def exchanges_df(self) -> pd.DataFrame:
        last_price = self.connectors[self.maker_exchange].get_price_by_type(self.maker_pair, self.price_source)
        maker_buy_result = self.connectors[self.maker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        maker_sell_result = self.connectors[self.maker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        maker_buy_spread_bps = (maker_buy_result.result_price - taker_buy_result.result_price) / last_price * 10000
        maker_sell_spread_bps = (taker_sell_result.result_price - maker_sell_result.result_price) / last_price * 10000
        columns = ["Exchange", "Market", "Last Price", "Buy Price", "Sell Price", "Buy Spread", "Sell Spread"]
        data = []
        data.append([
            self.maker_exchange,
            self.maker_pair,
            float(self.connectors[self.maker_exchange].get_price_by_type(self.maker_pair, self.price_source)),
            float(maker_buy_result.result_price),
            float(maker_sell_result.result_price),
            int(maker_buy_spread_bps),
            int(maker_sell_spread_bps)
        ])
        data.append([
            self.taker_exchange,
            self.taker_pair,
            float(self.connectors[self.taker_exchange].get_price_by_type(self.maker_pair, self.price_source)),
            float(taker_buy_result.result_price),
            float(taker_sell_result.result_price),
            int(-maker_buy_spread_bps),
            int(-maker_sell_spread_bps)
        ])
        df = pd.DataFrame(data=data, columns=columns)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        columns = ["Exchange", "Market", "Side", "Price", "Amount", "Spread Last", "Spread Cancel", "Age"]
        data = []
        last_price = self.connectors[self.maker_exchange].get_price_by_type(self.maker_pair, self.price_source)
        taker_buy_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, True,
                                                                                     self.order_amount)
        taker_sell_result = self.connectors[self.taker_exchange].get_price_for_volume(self.taker_pair, False,
                                                                                      self.order_amount)
        buy_cancel_threshold = taker_sell_result.result_price * Decimal(1 - self.min_spread_bps / 10000)
        sell_cancel_threshold = taker_buy_result.result_price * Decimal(1 + self.min_spread_bps / 10000)
        for connector_name, connector in self.connectors.items():
            for order in self.get_active_orders(connector_name):
                age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
                spread_last_bps = (last_price - order.price) / last_price * 10000 if order.is_buy \
                    else (order.price - last_price) / last_price * 10000
                spread_cancel_bps = (buy_cancel_threshold - order.price) / buy_cancel_threshold * 10000 if order.is_buy \
                    else (order.price - sell_cancel_threshold) / sell_cancel_threshold * 10000
                data.append([
                    self.maker_exchange,
                    order.trading_pair,
                    "buy" if order.is_buy else "sell",
                    float(order.price),
                    float(order.quantity),
                    int(spread_last_bps),
                    int(spread_cancel_bps),
                    age_txt
                ])
        if not data:
            raise ValueError
        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Market", "Side"], inplace=True)
        return df

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(
            ["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        exchanges_df = self.exchanges_df()
        lines.extend(
            ["", "  Exchanges:"] + ["    " + line for line in exchanges_df.to_string(index=False).split("\n")])

        try:
            orders_df = self.active_orders_df()
            lines.extend(
                ["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        return "\n".join(lines)
