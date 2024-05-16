import logging
import math
from decimal import Decimal
from typing import Dict

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class VWAPExample(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Simple-VWAP-Example-d43a929cc5bd45c6b1a72f63e6635618
    Video: -
    Description:
    This example lets you create one VWAP in a market using a percentage of the sum volume of the order book
    until a spread from the mid price.
    This example demonstrates:
      - How to get the account balance
      - How to get the bids and asks of a market
      - How to code a "utility" strategy
    """
    last_ordered_ts = 0
    vwap: Dict = {"connector_name": "binance_paper_trade", "trading_pair": "ETH-USDT", "is_buy": True,
                  "total_volume_usd": 1000, "price_spread": 0.001, "volume_perc": 0.001, "order_delay_time": 10}
    markets = {vwap["connector_name"]: {vwap["trading_pair"]}}

    def on_tick(self):
        """
         Every order delay time the strategy will buy or sell the base asset. It will compute the cumulative order book
         volume until the spread and buy a percentage of that.
         The input of the strategy is in USD, but we will use the rate oracle to get a target base that will be static.
         - Use the Rate Oracle to get a conversion rate
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
                        order_type=vwap_order_adjusted.order_type)
                    self.last_ordered_ts = self.current_timestamp

    def init_vwap_stats(self):
        # General parameters
        vwap = self.vwap.copy()
        vwap["connector"] = self.connectors[vwap["connector_name"]]
        vwap["delta"] = 0
        vwap["trades"] = []
        vwap["status"] = "ACTIVE"
        vwap["trade_type"] = TradeType.BUY if self.vwap["is_buy"] else TradeType.SELL
        base_asset, quote_asset = split_hb_trading_pair(vwap["trading_pair"])

        # USD conversion to quote and base asset
        conversion_base_asset = f"{base_asset}-USD"
        conversion_quote_asset = f"{quote_asset}-USD"
        base_conversion_rate = RateOracle.get_instance().get_pair_rate(conversion_base_asset)
        quote_conversion_rate = RateOracle.get_instance().get_pair_rate(conversion_quote_asset)
        vwap["start_price"] = vwap["connector"].get_price(vwap["trading_pair"], vwap["is_buy"])
        vwap["target_base_volume"] = vwap["total_volume_usd"] / base_conversion_rate
        vwap["ideal_quote_volume"] = vwap["total_volume_usd"] / quote_conversion_rate

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
