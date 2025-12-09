import os
from decimal import Decimal
from typing import Dict

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimpleXEMMConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    maker_connector: str = Field("kucoin_paper_trade", json_schema_extra={
        "prompt": "Maker connector where the bot will place maker orders", "prompt_on_new": True})
    maker_trading_pair: str = Field("ETH-USDT", json_schema_extra={
        "prompt": "Maker trading pair where the bot will place maker orders", "prompt_on_new": True})
    taker_connector: str = Field("binance_paper_trade", json_schema_extra={
        "prompt": "Taker connector where the bot will hedge filled orders", "prompt_on_new": True})
    taker_trading_pair: str = Field("ETH-USDT", json_schema_extra={
        "prompt": "Taker trading pair where the bot will hedge filled orders", "prompt_on_new": True})
    order_amount: Decimal = Field(0.1, json_schema_extra={
        "prompt": "Order amount (denominated in base asset)", "prompt_on_new": True})
    target_profitability: Decimal = Field(Decimal("0.001"), json_schema_extra={
        "prompt": "Target profitability (e.g., 0.01 for 1%)", "prompt_on_new": True})
    min_profitability: Decimal = Field(Decimal("0.0005"), json_schema_extra={
        "prompt": "Minimum profitability (e.g., 0.005 for 0.5%)", "prompt_on_new": True})
    max_order_age: int = Field(120, json_schema_extra={
        "prompt": "Max order age (in seconds)", "prompt_on_new": True})


class SimpleXEMM(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022 (updated May 2024)
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
        cls.markets = {config.maker_connector: {config.maker_trading_pair}, config.taker_connector: {config.taker_trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimpleXEMMConfig):
        super().__init__(connectors)
        self.config = config

    def on_tick(self):
        taker_buy_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, True, self.config.order_amount)
        taker_sell_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, False, self.config.order_amount)

        if not self.buy_order_placed:
            # Maker BUY: profitability = (taker_price - maker_price) / maker_price
            # To achieve target: maker_price = taker_price / (1 + target_profitability)
            maker_buy_price = taker_sell_result.result_price / (Decimal("1") + self.config.target_profitability)
            buy_order_amount = min(self.config.order_amount, self.buy_hedging_budget())

            buy_order = OrderCandidate(trading_pair=self.config.maker_trading_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.BUY, amount=Decimal(buy_order_amount), price=maker_buy_price)
            buy_order_adjusted = self.connectors[self.config.maker_connector].budget_checker.adjust_candidate(buy_order, all_or_none=False)
            self.buy(self.config.maker_connector, self.config.maker_trading_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)
            self.buy_order_placed = True

        if not self.sell_order_placed:
            # Maker SELL: profitability = (maker_price - taker_price) / maker_price
            # To achieve target: maker_price = taker_price / (1 - target_profitability)
            maker_sell_price = taker_buy_result.result_price / (Decimal("1") - self.config.target_profitability)
            sell_order_amount = min(self.config.order_amount, self.sell_hedging_budget())
            sell_order = OrderCandidate(trading_pair=self.config.maker_trading_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=TradeType.SELL, amount=Decimal(sell_order_amount), price=maker_sell_price)
            sell_order_adjusted = self.connectors[self.config.maker_connector].budget_checker.adjust_candidate(sell_order, all_or_none=False)
            self.sell(self.config.maker_connector, self.config.maker_trading_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)
            self.sell_order_placed = True

        for order in self.get_active_orders(connector_name=self.config.maker_connector):
            cancel_timestamp = order.creation_timestamp / 1000000 + self.config.max_order_age
            if order.is_buy:
                # Calculate current profitability: (taker_sell_price - maker_buy_price) / maker_buy_price
                current_profitability = (taker_sell_result.result_price - order.price) / order.price
                if current_profitability < self.config.min_profitability or cancel_timestamp < self.current_timestamp:
                    self.logger().info(f"Cancelling buy order: {order.client_order_id} (profitability: {current_profitability:.4f})")
                    self.cancel(self.config.maker_connector, order.trading_pair, order.client_order_id)
                    self.buy_order_placed = False
            else:
                # Calculate current profitability: (maker_sell_price - taker_buy_price) / maker_sell_price
                current_profitability = (order.price - taker_buy_result.result_price) / order.price
                if current_profitability < self.config.min_profitability or cancel_timestamp < self.current_timestamp:
                    self.logger().info(f"Cancelling sell order: {order.client_order_id} (profitability: {current_profitability:.4f})")
                    self.cancel(self.config.maker_connector, order.trading_pair, order.client_order_id)
                    self.sell_order_placed = False
        return

    def buy_hedging_budget(self) -> Decimal:
        base_asset = self.config.taker_trading_pair.split("-")[0]
        balance = self.connectors[self.config.taker_connector].get_available_balance(base_asset)
        return balance

    def sell_hedging_budget(self) -> Decimal:
        quote_asset = self.config.taker_trading_pair.split("-")[1]
        balance = self.connectors[self.config.taker_connector].get_available_balance(quote_asset)
        taker_buy_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, True, self.config.order_amount)
        return balance / taker_buy_result.result_price

    def is_active_maker_order(self, event: OrderFilledEvent):
        """
        Helper function that checks if order is an active order on the maker exchange
        """
        for order in self.get_active_orders(connector_name=self.config.maker_connector):
            if order.client_order_id == event.order_id:
                return True
        return False

    def did_fill_order(self, event: OrderFilledEvent):
        if event.trade_type == TradeType.BUY and self.is_active_maker_order(event):
            self.logger().info(f"Filled maker buy order at price {event.price:.6f} for amount {event.amount:.2f}")
            self.place_sell_order(self.config.taker_connector, self.config.taker_trading_pair, event.amount)
            self.buy_order_placed = False
        else:
            if event.trade_type == TradeType.SELL and self.is_active_maker_order(event):
                self.logger().info(f"Filled maker sell order at price {event.price:.6f} for amount {event.amount:.2f}")
                self.place_buy_order(self.config.taker_connector, self.config.taker_trading_pair, event.amount)
                self.sell_order_placed = False

    def place_buy_order(self, exchange: str, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.LIMIT):
        buy_result = self.connectors[exchange].get_price_for_volume(trading_pair, True, amount)
        buy_order = OrderCandidate(trading_pair=trading_pair, is_maker=False, order_type=order_type, order_side=TradeType.BUY, amount=amount, price=buy_result.result_price)
        buy_order_adjusted = self.connectors[exchange].budget_checker.adjust_candidate(buy_order, all_or_none=False)
        self.buy(exchange, trading_pair, buy_order_adjusted.amount, buy_order_adjusted.order_type, buy_order_adjusted.price)

    def place_sell_order(self, exchange: str, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.LIMIT):
        sell_result = self.connectors[exchange].get_price_for_volume(trading_pair, False, amount)
        sell_order = OrderCandidate(trading_pair=trading_pair, is_maker=False, order_type=order_type, order_side=TradeType.SELL, amount=amount, price=sell_result.result_price)
        sell_order_adjusted = self.connectors[exchange].budget_checker.adjust_candidate(sell_order, all_or_none=False)
        self.sell(exchange, trading_pair, sell_order_adjusted.amount, sell_order_adjusted.order_type, sell_order_adjusted.price)

    def exchanges_df(self) -> pd.DataFrame:
        """
        Return a custom data frame of prices on maker vs taker exchanges for display purposes
        """
        maker_mid_price = self.connectors[self.config.maker_connector].get_mid_price(self.config.maker_trading_pair)
        maker_buy_result = self.connectors[self.config.maker_connector].get_price_for_volume(self.config.maker_trading_pair, True, self.config.order_amount)
        maker_sell_result = self.connectors[self.config.maker_connector].get_price_for_volume(self.config.maker_trading_pair, False, self.config.order_amount)
        taker_buy_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, True, self.config.order_amount)
        taker_sell_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, False, self.config.order_amount)
        taker_mid_price = self.connectors[self.config.taker_connector].get_mid_price(self.config.taker_trading_pair)

        columns = ["Exchange", "Market", "Mid Price", "Buy Price", "Sell Price"]
        data = []
        data.append([
            self.config.maker_connector,
            self.config.maker_trading_pair,
            float(maker_mid_price),
            float(maker_buy_result.result_price),
            float(maker_sell_result.result_price)
        ])
        data.append([
            self.config.taker_connector,
            self.config.taker_trading_pair,
            float(taker_mid_price),
            float(taker_buy_result.result_price),
            float(taker_sell_result.result_price)
        ])
        df = pd.DataFrame(data=data, columns=columns)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        """
        Returns a custom data frame of all active maker orders for display purposes
        """
        columns = ["Exchange", "Market", "Side", "Price", "Amount", "Current Profit %", "Min Profit %", "Age"]
        data = []
        taker_buy_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, True, self.config.order_amount)
        taker_sell_result = self.connectors[self.config.taker_connector].get_price_for_volume(self.config.taker_trading_pair, False, self.config.order_amount)
        for connector_name, connector in self.connectors.items():
            for order in self.get_active_orders(connector_name):
                age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
                if order.is_buy:
                    # Buy profitability: (taker_sell_price - maker_buy_price) / maker_buy_price
                    current_profitability = (taker_sell_result.result_price - order.price) / order.price * 100
                else:
                    # Sell profitability: (maker_sell_price - taker_buy_price) / maker_sell_price
                    current_profitability = (order.price - taker_buy_result.result_price) / order.price * 100

                data.append([
                    self.config.maker_connector,
                    order.trading_pair,
                    "buy" if order.is_buy else "sell",
                    float(order.price),
                    float(order.quantity),
                    f"{float(current_profitability):.3f}",
                    f"{float(self.config.min_profitability * 100):.3f}",
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
