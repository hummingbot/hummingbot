import logging
import math
from decimal import Decimal
from typing import Dict

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

# Based on vwapmm Example /hummingbot/scripts/smple_vwapmm_example.py
# Using vwapmmExample to guide a Market Making strategy,based on a simplified AvellandaStoikov strategy


class vwapmm_MM_Rewards(ScriptStrategyBase):
    """
    IMPORTANT: To run this example select CoinGecko as Rate Oracle.
    This example lets you create one vwapmm in a market using a percentage of the sum volume of the order book
    until a spread from the mid price.
    """
    last_ordered_ts = 0
    vwapmm: Dict = {"connector_name": "binance_paper_trade",
                    "trading_pair": "ETH-USDT",
                    "is_buy": True,
                    "total_volume_usd": 20000,  # Episode Size
                    "price_spread": 0.00025,
                    "volume_perc": 0.001,
                    "order_delay_time": 10,
                    "order_stale_factor": 5
                    }
    markets = {vwapmm["connector_name"]: {vwapmm["trading_pair"]}}

    def on_tick(self):
        # """
        # Every order delay time the strategy will place buy and sell limit orders of the base asset.
        # It will compute the cumulative order book volume until the spread and buy a percentage of that.
        # The input of the strategy is in USD, but we will use the rate oracle to get a target base that will be static.
        # - Use the Rate Oracle to get a conversion rate
        # - Create proposal (a list of order candidates)
        # - Check the account balance and adjust the proposal accordingly (lower order amount if needed)
        # - Lastly, execute the proposal on the exchange
        # """
        if self.last_ordered_ts < (self.current_timestamp - self.vwapmm["order_delay_time"]):
            if self.vwapmm.get("status") is None:
                self.init_vwapmm_stats()
            elif self.vwapmm.get("status") == "ACTIVE":
                # Cancel any orders still remaining after delay_time * stale_factor time increment. Need fresh slate for strategy.
                # if self.last_ordered_ts < (self.current_timestamp - (self.vwapmm["order_stale_factor"] * self.vwapmm["order_delay_time"])):
                #     live_orders = self.get_active_orders(self.vwapmm["connector_name"])
                #     if len(live_orders) > 0:
                #         for ao in live_orders:
                #             self.cancel(self.vwapmm["connector_name"], self.vwapmm["trading_pair"], ao.client_order_id)
                #             self.logger().info(f"LimitOrder cancelled: exch:{self.vwapmm['connector_name']} pair:{self.vwapmm['trading_pair']}, id:{ao.client_order_id}")
                #         return #HACK: Waste a time increment to cancel all open orders. Only want limited BUY and SELL limit orders active.
                self.vwapmm["is_buy"] = False
                vwapmm_order: OrderCandidate = self.create_order()
                vwapmm_order_adjusted = self.vwapmm["connector"].budget_checker.adjust_candidate(vwapmm_order, all_or_none=True)
                self.vwapmm["is_buy"] = True  # ping-pong buy-sell, do before create_order()
                vwapmm_order_opp: OrderCandidate = self.create_order()
                vwapmm_order_adjusted_opp = self.vwapmm["connector"].budget_checker.adjust_candidate(vwapmm_order_opp, all_or_none=True)

                # First Side
                if math.isclose(vwapmm_order_adjusted.amount, Decimal("0"), rel_tol=1E-5):
                    self.logger().info(f"Order adjusted: {vwapmm_order_adjusted.amount}, too low to place an order")
                else:
                    self.vwapmm["is_buy"] = True
                    self.place_order(
                        connector_name=self.vwapmm["connector_name"],
                        trading_pair=self.vwapmm["trading_pair"],
                        is_buy=self.vwapmm["is_buy"],
                        amount=vwapmm_order_adjusted.amount,
                        order_type=vwapmm_order_adjusted.order_type,
                        price=vwapmm_order_adjusted.price)

                # Opposite Side
                if math.isclose(vwapmm_order_adjusted_opp.amount, Decimal("0"), rel_tol=1E-5):
                    self.logger().info(f"Order adjusted_opp: {vwapmm_order_adjusted_opp.amount}, too low to place an order")
                else:
                    self.vwapmm["is_buy"] = False
                    self.place_order(
                        connector_name=self.vwapmm["connector_name"],
                        trading_pair=self.vwapmm["trading_pair"],
                        is_buy=self.vwapmm["is_buy"],
                        amount=vwapmm_order_adjusted_opp.amount,
                        order_type=vwapmm_order_adjusted_opp.order_type,
                        price=vwapmm_order_adjusted_opp.price)
            elif self.vwapmm.get("status") == "COMPLETE":
                bal_df = self.get_balance_df()
                act_orders = self.get_active_orders(self.vwapmm["connector_name"])
                if len(act_orders) > 0:
                    active_orders_df = self.active_orders_df()
                else:
                    active_orders_df = "No active orders"

                msg = (f"Balances - {bal_df}"
                       f"Active Orders - {active_orders_df}"
                       )

                self.log_with_clock(logging.INFO, msg)
                self.notify_hb_app_with_timestamp(msg)

            self.last_ordered_ts = self.current_timestamp

    def init_vwapmm_stats(self):
        # General parameters
        vwapmm = self.vwapmm.copy()
        vwapmm["connector"] = self.connectors[vwapmm["connector_name"]]
        vwapmm["delta"] = 0
        vwapmm["delta_opposite"] = 0
        vwapmm["trades"] = []
        vwapmm["status"] = "ACTIVE"
        vwapmm["trade_type"] = TradeType.BUY if self.vwapmm["is_buy"] else TradeType.SELL
        base_asset, quote_asset = split_hb_trading_pair(vwapmm["trading_pair"])

        # USD conversion to quote and base asset
        conversion_base_asset = f"{base_asset}-USD"
        conversion_quote_asset = f"{quote_asset}-USD"
        base_conversion_rate = RateOracle.get_instance().get_pair_rate(conversion_base_asset)
        quote_conversion_rate = RateOracle.get_instance().get_pair_rate(conversion_quote_asset)
        vwapmm["start_price"] = vwapmm["connector"].get_price(vwapmm["trading_pair"], vwapmm["is_buy"])
        vwapmm["target_base_volume"] = vwapmm["total_volume_usd"] / base_conversion_rate
        vwapmm["target_base_volume_opposite"] = vwapmm["total_volume_usd"] / base_conversion_rate
        vwapmm["ideal_quote_volume"] = vwapmm["total_volume_usd"] / quote_conversion_rate

        # Compute market order scenario
        orderbook_query = vwapmm["connector"].get_quote_volume_for_base_amount(vwapmm["trading_pair"], vwapmm["is_buy"], vwapmm["target_base_volume"])
        vwapmm["market_order_base_volume"] = orderbook_query.query_volume
        vwapmm["market_order_quote_volume"] = orderbook_query.result_volume
        vwapmm["volume_remaining"] = vwapmm["target_base_volume"]
        vwapmm["volume_remaining_opposite"] = vwapmm["target_base_volume"]
        vwapmm["real_quote_volume"] = Decimal(0)
        vwapmm["real_quote_volume_opposite"] = Decimal(0)
        self.vwapmm = vwapmm

    def create_order(self) -> OrderCandidate:
        """
         Retrieves the cumulative volume of the order book until the price spread is reached, then takes a percentage
         of that to use as order amount.
         """
        # Compute the new price using the max spread allowed
        mid_price = float(self.vwapmm["connector"].get_mid_price(self.vwapmm["trading_pair"]))
        price_multiplier = 1 + self.vwapmm["price_spread"] if self.vwapmm["is_buy"] else 1 - self.vwapmm["price_spread"]
        price_affected_by_spread = mid_price * price_multiplier

        # Query the cumulative volume until the price affected by spread
        orderbook_query = self.vwapmm["connector"].get_volume_for_price(
            trading_pair=self.vwapmm["trading_pair"],
            is_buy=self.vwapmm["is_buy"],
            price=price_affected_by_spread)
        volume_for_price = orderbook_query.result_volume

        # Check if the volume available is higher than the remaining
        amount = min(volume_for_price * Decimal(self.vwapmm["volume_perc"]), Decimal(self.vwapmm["volume_remaining"]))

        # Quantize the order amount and price
        amount = self.vwapmm["connector"].quantize_order_amount(self.vwapmm["trading_pair"], amount)
        price = self.vwapmm["connector"].quantize_order_price(self.vwapmm["trading_pair"], Decimal(price_affected_by_spread))
        self.vwapmm["trade_type"] = TradeType.BUY if self.vwapmm["is_buy"] else TradeType.SELL
        # Create the Order Candidate
        vwapmm_order = OrderCandidate(
            trading_pair=self.vwapmm["trading_pair"],
            is_maker=False,
            order_type=OrderType.LIMIT,  # OrderType.MARKET,
            order_side=self.vwapmm["trade_type"],
            amount=amount,
            price=price)
        return vwapmm_order

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
        if event.trading_pair == self.vwapmm["trading_pair"] and (event.trade_type.name == 'BUY' or event.trade_type.name == 'SELL'):
            if event.trade_type.name == "BUY":  # BUY
                self.vwapmm["volume_remaining"] -= event.amount
                self.vwapmm["delta"] = (self.vwapmm["target_base_volume"] - self.vwapmm["volume_remaining"]) / self.vwapmm[
                    "target_base_volume"]
                self.vwapmm["real_quote_volume"] += event.price * event.amount

            else:  # SELL
                self.vwapmm["volume_remaining_opposite"] -= event.amount
                self.vwapmm["delta_opposite"] = (self.vwapmm["target_base_volume"] - self.vwapmm["volume_remaining_opposite"]) / self.vwapmm[
                    "target_base_volume"]
                self.vwapmm["real_quote_volume_opposite"] += event.price * event.amount

            self.vwapmm["trades"].append(event)

            if ((self.vwapmm["delta"] >= 1.0)
                or (self.vwapmm["delta_opposite"] >= 1.0)
                or math.isclose(self.vwapmm["delta"], 1, rel_tol=1e-5)
                    or math.isclose(self.vwapmm["delta_opposite"], 1, rel_tol=1e-5)):

                self.vwapmm["status"] = "COMPLETE"

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
        lines.extend(["", "vwapmm Info:"] + ["   " + key + ": " + value
                                             for key, value in self.vwapmm.items()
                                             if type(value) == str])

        lines.extend(["", "vwapmm Stats:"] + ["   " + key + ": " + str(round(value, 4))
                                              for key, value in self.vwapmm.items()
                                              if type(value) in [int, float, Decimal]])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
