import logging
from decimal import Decimal
from typing import Dict

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AVWAPExample(ScriptStrategyBase):
    """
    This example lets you create one VWAP in a market using a percentage of the sum volume of the order book
    until a spread from the mid price.
    This example demonstrates:
      - How to get the account balance
      - How to get the bids and asks of a market
      - How to code a "utility" strategy
    """
    last_ordered_ts = 0
    vwap: Dict = dict(connector_name="binance_paper_trade", trading_pair="ETH-USDT", is_buy=True,
                      total_volume_usd=100000, price_spread=0.002, volume_perc=0.001, order_delay_time=10)
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
                vwap_order_adjusted = self.vwap["connector"].budget_checker.adjust_candidate(vwap_order, all_or_none=False)
                if vwap_order_adjusted.amount > Decimal("0"):
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
        vwap["status"] = "ACTIVE"
        base_asset, quote_asset = split_hb_trading_pair(vwap["trading_pair"])

        # USD conversion to quote and base asset
        conversion_base_asset = f"{base_asset}-USD"
        conversion_quote_asset = f"{quote_asset}-USD"
        base_conversion_rate = RateOracle.get_instance().rate(conversion_base_asset)
        quote_conversion_rate = RateOracle.get_instance().rate(conversion_quote_asset)
        vwap["target_base_volume"] = vwap["total_volume_usd"] / base_conversion_rate
        vwap["volume_remaining"] = vwap["target_base_volume"]
        vwap["ideal_quote_volume"] = vwap["total_volume_usd"] / quote_conversion_rate
        vwap["start_price"] = vwap["connector"].get_price(vwap["trading_pair"], vwap["is_buy"])

        # Compute market order scenario
        orderbook_query = vwap["connector"].get_quote_volume_for_base_amount(vwap["trading_pair"], vwap["is_buy"], vwap["target_base_volume"])
        vwap["market_order_base_volume"] = orderbook_query.query_volume
        vwap["market_order_quote_volume"] = orderbook_query.result_volume
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

        # Create the Order Candidate
        vwap_order = OrderCandidate(
            trading_pair=self.vwap["trading_pair"],
            is_maker=False,
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY if self.vwap["is_buy"] else TradeType.SELL,
            amount=volume_for_price * Decimal(self.vwap["volume_perc"]),
            price=Decimal(price_affected_by_spread))
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
        Listens to fill order event to log it and notify the hummingbot application.
        If you set up Telegram bot, you will get notification there as well.
        """
        msg = (f"({event.trading_pair}) {event.trade_type.name} order (price: {event.price}) of {event.amount} "
               f"{split_hb_trading_pair(event.trading_pair)[0]} is filled.")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
