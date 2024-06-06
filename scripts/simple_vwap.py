import logging
import math
import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class VWAPConfig(BaseClientModel):
    """
    Configuration parameters for the VWAP strategy.
    """

    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector_name: str = Field("binance_paper_trade", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will place orders"))
    trading_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair where the bot will place orders"))
    is_buy: bool = Field(True, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Buying or selling the base asset? (True for buy, False for sell)"))
    total_volume_quote: Decimal = Field(1000, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Total amount to buy/sell (in quote asset)"))
    price_spread: float = Field(0.001, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Spread used to calculate the order price"))
    volume_perc: float = Field(0.001, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Maximum percentage of the order book volume to buy/sell"))
    order_delay_time: int = Field(10, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Delay time between orders (in seconds)"))


class VWAPExample(ScriptStrategyBase):
    """
    BotCamp Cohort: 7 (Apr 2024)
    Description:
    This is an updated version of simple_vwap_example.py. Changes include:
    - Users can define script configuration parameters
    - Total volume is expressed in quote asset rather than USD
    - Use of the rate oracle has been removed
    """

    @classmethod
    def init_markets(cls, config: VWAPConfig):
        cls.markets = {config.connector_name: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: VWAPConfig):
        super().__init__(connectors)
        self.config = config
        self.initialized = False
        self.vwap: Dict = {"connector_name": self.config.connector_name,
                           "trading_pair": self.config.trading_pair,
                           "is_buy": self.config.is_buy,
                           "total_volume_quote": self.config.total_volume_quote,
                           "price_spread": self.config.price_spread,
                           "volume_perc": self.config.volume_perc,
                           "order_delay_time": self.config.order_delay_time}

    last_ordered_ts = 0

    def on_tick(self):
        """
         Every order delay time the strategy will buy or sell the base asset. It will compute the cumulative order book
         volume until the spread and buy a percentage of that.
         The input of the strategy is in quote, and we will convert at initial price to get a target base that will be static.
         - Create proposal (a list of order candidates)
         - Check the account balance and adjust the proposal accordingly (lower order amount if needed)
         - Lastly, execute the proposal on the exchange
         """
        if self.last_ordered_ts < (self.current_timestamp - self.vwap["order_delay_time"]):
            if self.vwap.get("status") is None:
                self.init_vwap_stats()
            elif self.vwap.get("status") == "ACTIVE":
                vwap_order: OrderCandidate = self.create_order()
                vwap_order_adjusted = self.vwap["connector"].budget_checker.adjust_candidate(vwap_order,
                                                                                             all_or_none=False)
                if math.isclose(vwap_order_adjusted.amount, Decimal("0"), rel_tol=1E-5):
                    self.logger().info(f"Order adjusted: {vwap_order_adjusted.amount}, too low to place an order")
                else:
                    self.place_order(
                        connector_name=self.vwap["connector_name"],
                        trading_pair=self.vwap["trading_pair"],
                        is_buy=self.vwap["is_buy"],
                        amount=vwap_order_adjusted.amount,
                        order_type=vwap_order_adjusted.order_type,
                        price=vwap_order_adjusted.price)
                    self.last_ordered_ts = self.current_timestamp

    def init_vwap_stats(self):
        # General parameters
        vwap = self.vwap.copy()
        vwap["connector"] = self.connectors[vwap["connector_name"]]
        vwap["delta"] = 0
        vwap["trades"] = []
        vwap["status"] = "ACTIVE"
        vwap["trade_type"] = TradeType.BUY if self.vwap["is_buy"] else TradeType.SELL
        vwap["start_price"] = vwap["connector"].get_price(vwap["trading_pair"], vwap["is_buy"])
        vwap["target_base_volume"] = vwap["total_volume_quote"] / vwap["start_price"]

        # Compute market order scenario
        orderbook_query = vwap["connector"].get_quote_volume_for_base_amount(vwap["trading_pair"], vwap["is_buy"],
                                                                             vwap["target_base_volume"])
        vwap["market_order_base_volume"] = orderbook_query.query_volume
        vwap["market_order_quote_volume"] = orderbook_query.result_volume
        vwap["volume_remaining"] = vwap["target_base_volume"]
        vwap["real_quote_volume"] = Decimal(0)
        self.vwap = vwap

    def create_order(self) -> OrderCandidate:
        """
         Retrieves the cumulative volume of the order book until the price spread is reached, then takes a percentage
         of that to use as order amount.
         """
        # Compute the new price using the max spread allowed
        mid_price = float(self.vwap["connector"].get_mid_price(self.vwap["trading_pair"]))
        price_multiplier = 1 + self.vwap["price_spread"] if self.vwap["is_buy"] else 1 - self.vwap["price_spread"]
        price_affected_by_spread = mid_price * price_multiplier

        # Query the cumulative volume until the price affected by spread
        orderbook_query = self.vwap["connector"].get_volume_for_price(
            trading_pair=self.vwap["trading_pair"],
            is_buy=self.vwap["is_buy"],
            price=price_affected_by_spread)
        volume_for_price = orderbook_query.result_volume

        # Check if the volume available is higher than the remaining
        amount = min(volume_for_price * Decimal(self.vwap["volume_perc"]), Decimal(self.vwap["volume_remaining"]))

        # Quantize the order amount and price
        amount = self.vwap["connector"].quantize_order_amount(self.vwap["trading_pair"], amount)
        price = self.vwap["connector"].quantize_order_price(self.vwap["trading_pair"],
                                                            Decimal(price_affected_by_spread))
        # Create the Order Candidate
        vwap_order = OrderCandidate(
            trading_pair=self.vwap["trading_pair"],
            is_maker=False,
            order_type=OrderType.MARKET,
            order_side=self.vwap["trade_type"],
            amount=amount,
            price=price)
        return vwap_order

    def place_order(self,
                    connector_name: str,
                    trading_pair: str,
                    is_buy: bool,
                    amount: Decimal,
                    order_type: OrderType,
                    price=Decimal("NaN"),
                    ):
        if is_buy:
            self.buy(connector_name, trading_pair, amount, order_type, price)
        else:
            self.sell(connector_name, trading_pair, amount, order_type, price)

    def did_fill_order(self, event: OrderFilledEvent):
        """
         Listens to fill order event to log it and notify the Hummingbot application.
         If you set up Telegram bot, you will get notification there as well.
         """
        if event.trading_pair == self.vwap["trading_pair"] and event.trade_type == self.vwap["trade_type"]:
            self.vwap["volume_remaining"] -= event.amount
            self.vwap["delta"] = (self.vwap["target_base_volume"] - self.vwap["volume_remaining"]) / self.vwap[
                "target_base_volume"]
            self.vwap["real_quote_volume"] += event.price * event.amount
            self.vwap["trades"].append(event)
            if math.isclose(self.vwap["delta"], 1, rel_tol=1e-5):
                self.vwap["status"] = "COMPLETE"
        msg = (f"({event.trading_pair}) {event.trade_type.name} order (price: {round(event.price, 2)}) of "
               f"{round(event.amount, 2)} "
               f"{split_hb_trading_pair(event.trading_pair)[0]} is filled.")

        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

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

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])
        lines.extend(["", "VWAP Info:"] + ["   " + key + ": " + value
                                           for key, value in self.vwap.items()
                                           if isinstance(value, str)])

        lines.extend(["", "VWAP Stats:"] + ["   " + key + ": " + str(round(value, 4))
                                            for key, value in self.vwap.items()
                                            if type(value) in [int, float, Decimal]])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
