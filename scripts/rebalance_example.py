import logging

from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent
)
from hummingbot.strategy.script_strategy_base import Decimal
from typing import Dict

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.event.events import  OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
class Rebalance_example(ScriptStrategyBase):
    """
    This example shows how to rebalnce
    """

    last_ordered_ts = 0.
    #Set Variable
    rb: Dict = {
        "connector_name": "kucoin_paper_trade",
        "trading_pair": "BTC-USDT",
        "is_buy": True,
        "threshold": 0.01,
        "targe_value": 5000,
        "status": ""
    }
    markets = {rb["connector_name"]:{rb["trading_pair"]}}
    buy_interval = 10.
    price = 0
    activate_order_id = ""



    def on_tick(self):
        # Check if it is time to buy
        if self.last_ordered_ts < (self.current_timestamp - self.buy_interval):
            # Calculate the value of current asset A, calculate the value of current asset B, convert to USDT
            # If the value of asset A is more than the targe_value*(1+threshold) then sell
            # If the value of asset A is less than the set ratio + threshold then buy
            # If neither, do nothing
            if self.rb.get("status") == "":
                self.init_rebalance()
            elif self.rb["status"] == "ACTIVATE":
                self.cancel_all_order()
                self.get_balance()
                self.create_order()

            self.last_ordered_ts = self.current_timestamp

    def cancel_all_order(self):
        active_orders = self.get_active_orders(self.rb["connector_name"])
        for order in active_orders:
            self.cancel(self.rb["connector_name"], self.rb["trading_pair"],order.client_order_id)

    def init_rebalance(self):
        self.rb["status"] = "ACTIVATE"
        base, quote = split_hb_trading_pair(self.rb["trading_pair"])
        self.rb["base"] = base
        self.rb["quote"] = quote
        self.rb["start_price"] = self.connectors(self.rb["connector_name"]).get_mid_price(self.rb["trading_pair"])

    def get_balance(self):
        df = self.get_balance_df()
        self.rb["base_asset"] = float(df.loc[df['Asset'] == self.rb["base"], 'Total Balance'])
        self.price = float(self.connectors[self.rb["connector_name"]].get_price(self.rb["trading_pair"], False))
        self.rb["base_value"] = self.rb["base_asset"] * self.price
        self.rb["quote_asset"] = float(df.loc[df['Asset'] == self.rb["quote"], 'Total Balance'])

    def create_order(self):
        rb = self.rb.copy()
        if rb["base_value"] >= rb["targe_value"]* (1 + rb["threshold"]):
            self.sell(rb["connector_name"], rb["trading_pair"], Decimal(rb["base_asset"] * rb["threshold"]), OrderType.LIMIT, Decimal(self.price * 1.0001))
        elif rb["base_value"] < rb["targe_value"]* (1 - rb["threshold"]):
            self.buy(rb["connector_name"], rb["trading_pair"], Decimal(rb["base_asset"] * rb["threshold"]), OrderType.LIMIT, Decimal(self.price * 0.9999))

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        """
        Method called when the connector notifies a buy order has been created
        """
        self.logger().info(logging.INFO, f"The buy order {event.order_id} has been created")

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        """
        Method called when the connector notifies a sell order has been created
        """
        self.logger().info(logging.INFO, f"The sell order {event.order_id} has been created")

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

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)


