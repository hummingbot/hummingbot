import os
from decimal import Decimal
from typing import Dict

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimpleXEMMConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    maker_exchange: str = Field("kucoin_paper_trade", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Maker exchange where the bot will place maker orders"))
    maker_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Maker pair where the bot will place maker orders"))
    taker_exchange: str = Field("binance_paper_trade", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Taker exchange where the bot will hedge filled orders"))
    taker_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Taker pair where the bot will hedge filled orders"))
    order_amount: Decimal = Field(0.1, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (denominated in base asset)"))
    spread_bps: Decimal = Field(10, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Spread between maker and taker orders (in basis points)"))
    min_spread_bps: Decimal = Field(0, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Minimum spread (in basis points)"))
    slippage_buffer_spread_bps: Decimal = Field(100, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Slippage buffer (in basis points)"))
    max_order_age: int = Field(120, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Max order age (in seconds)"))


class SimpleXEMM(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Simple-XEMM-Example-f08cf7546ea94a44b389672fd21bb9ad
    Video: https://www.loom.com/share/ca08fe7bc3d14ba68ae704305ac78a3a
    Description:
    A simplified version of Hummingbot cross-exchange market making strategy, this bot makes a market on
    the maker pair and hedges any filled trades in the taker pair. If the spread (difference between maker order price
    and taker hedge price) dips below min_spread, the bot refreshes the order
    """

    buy_order_placed = False
    sell_order_placed = False

    @classmethod
    def init_markets(cls, config: SimpleXEMMConfig):
        cls.markets = {config.maker_exchange: {config.maker_pair}, config.taker_exchange: {config.taker_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimpleXEMMConfig):
        super().__init__(connectors)
        self.config = config
        self.maker_exchange = self.config.maker_exchange
        self.maker_pair = self.config.maker_pair
        self.taker_exchange = self.config.taker_exchange
        self.taker_pair = self.config.taker_pair
        self.order_amount = self.config.order_amount
        self.spread_bps = self.config.spread_bps
        self.min_spread_bps = self.config.min_spread_bps
        self.slippage_buffer_spread_bps = self.config.slippage_buffer_spread_bps
        self.max_order_age = self.config.max_order_age

    def on_tick(self):
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
        maker_buy_result = self.connectors[self.maker_exchange].get_price_for_volume(self.maker_pair, True, self.order_amount)
        maker_sell_result = self.connectors[self.maker_exchange].get_price_for_volume(self.maker_pair, False, self.order_amount)
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
            float(self.connectors[self.taker_exchange].get_mid_price(self.taker_pair)),
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

        return "\n".join(lines)
