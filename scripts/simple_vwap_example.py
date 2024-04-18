import logging
import os
from decimal import Decimal
from typing import Dict

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_book_query_result import ClientOrderBookQueryResult
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimpleVWAPConfig(BaseClientModel):
    """
    Configuration parameters for the SimpleVWAP strategy.
    """
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field("kraken_paper_trade", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the exchange where the bot will trade:"))
    trading_pair: str = Field("DOT-USDT", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the trading pair where the bot will place orders:"))
    is_buy: bool = Field(True, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Are you buying or selling the base asset? (True for buy, False for sell):"))
    total_amount_quote: Decimal = Field(100000, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the total amount to buy/sell (in quote asset):"))
    slippage_limit_pct: Decimal = Field(0.05, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the maximum slippage per order (in %):"))
    order_decrement_pct: Decimal = Field(5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "How much should the bot decrease each order to lower slippage (in %):"))
    filled_order_delay: int = Field(10, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "How long should the bot wait after an order fill (in seconds)?:"))


class SimpleVWAP(ScriptStrategyBase):
    """
    This strategy helps a user automate a series or buy or sell orders to achieve a desired total trading volume, while minimizing market impact. It configures dynamic order sizing and timing to optimize trade execution.
    """

    @classmethod
    def init_markets(cls, config: SimpleVWAPConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimpleVWAPConfig):
        super().__init__(connectors)
        self.config = config
        self.initialized = False

    # Assumptions
    price_source = PriceType.MidPrice       # PriceType.LastTrade
    order_type = OrderType.LIMIT            # OrderType.MARKET
    is_maker = False                        # True for maker orders
    minimum_amount_quote = 1                # Bot stops when remaining quote amount is below this value

    def on_tick(self):
        if self.initialized is False:
            self.initialize()

        if (self.current_timestamp > self.delay_timestamp) and (self.waiting_for_fill is False):
            # Determine remaining amount to buy/sell
            price = self.connectors[self.config.exchange].get_price_by_type(self.config.trading_pair, self.price_source)
            current_amount_base = self.remaining_amount_quote / price

            # Decrement the order size until slippage is lower than slippage limit
            (order_amount, vwap_price) = self.get_amount_for_slippage(current_amount_base, price)

            # Place the order and wait for it to be filled
            if order_amount * vwap_price > self.minimum_amount_quote:
                self.place_order(order_amount, vwap_price)
                self.waiting_for_fill = True
            else:
                slippage = self.calc_slippage(vwap_price, price)
                self.notify_hb_app_with_timestamp(f"Slippage limit exceeded - {order_amount:.2f} order results in {slippage * 100:.2f}% slippage.")
                self.delay_timestamp = self.current_timestamp + self.config.filled_order_delay

    # Initialize bot settings
    def initialize(self):
        self.create_timestamp = self.delay_timestamp = self.current_timestamp
        self.remaining_amount_quote = self.config.total_amount_quote

        # Calculate the price if you buy/sell total amount in one shot
        price = self.connectors[self.config.exchange].get_price_by_type(self.config.trading_pair, self.price_source)
        ideal_amount_base = self.config.total_amount_quote / price
        vwap = self.get_vwap(ideal_amount_base, price)

        # Initialize reporting data structures
        self.summary: Dict = {'1-shot Price': vwap.result_price, 'VWAP Price': 0, 'Base Amount Transacted': 0, 'Quote Amount Transacted': 0, 'P&L vs 1-shot': 0}
        self.fills = []
        self.waiting_for_fill = False
        self.initialized = True

    # Decrement the order amount until the implied slippage is lower than slippage limit
    def get_amount_for_slippage(self, amount: Decimal, price: Decimal) -> Decimal:
        decrement = (self.config.order_decrement_pct / 100) * amount
        while amount > 0:
            vwap = self.get_vwap(amount, price)
            slippage = self.calc_slippage(vwap.result_price, price)
            if slippage < self.config.slippage_limit_pct / 100:
                break
            amount -= decrement
        return (amount, vwap.result_price)

    # Get the VWAP price and volume for a given amount
    def get_vwap(self, amount: Decimal, ref_price: Decimal) -> ClientOrderBookQueryResult:
        # Determine the VWAP price and volume for the maximum order amount
        result = self.connectors[self.config.exchange].get_vwap_for_volume(
            self.config.trading_pair,
            self.config.is_buy,
            amount)
        slippage = self.calc_slippage(result.result_price, ref_price)
        trade_type = "buy" if self.config.is_buy else "sell"
        msg = (f"VWAP: {trade_type} {result.result_volume:.2f} for {result.result_price:.6f} | Slippage: {slippage * 100:.2f}%")
        self.log_with_clock(logging.INFO, msg)
        return result

    # Calculate slippage for two prices
    def calc_slippage(self, price: Decimal, ref_price: Decimal) -> Decimal:
        slippage = float(price) / float(ref_price) - 1 if self.config.is_buy else 1 - float(price) / float(ref_price)
        return slippage

    # Place an order
    def place_order(self, amount, price):
        # Create order proposal
        order = OrderCandidate(trading_pair=self.config.trading_pair,
                               is_maker=self.is_maker,
                               order_type=self.order_type,
                               order_side=TradeType.BUY if self.config.is_buy else TradeType.SELL,
                               amount=amount,
                               price=price)
        # Adjust order amount and price to budget and exchange rules
        order = self.connectors[self.config.exchange].budget_checker.adjust_candidate(order, all_or_none=False)

        # Place the order
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=self.config.exchange, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=self.config.exchange, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    # Handle order fill event
    def did_fill_order(self, event: OrderFilledEvent):
        # Notify the user when the order has been filled
        msg = (f"{event.trade_type.name} {event.amount:.2f} {event.trading_pair} at {event.price}")
        self.notify_hb_app_with_timestamp(msg)

        # Calculate metrics
        self.remaining_amount_quote -= event.amount * event.price

        # Update data structures
        self.fills.append({'Timestamp': self.current_timestamp,
                           'Type': event.trade_type.name,
                           'Amount': event.amount.quantize(Decimal('0.01')),
                           'Price': event.price.quantize(Decimal('0.000001'))})

        self.summary['Base Amount Transacted'] += event.amount
        self.summary['Quote Amount Transacted'] += event.amount * event.price
        self.summary['VWAP Price'] = self.summary['Quote Amount Transacted'] / self.summary['Base Amount Transacted']
        self.summary['P&L vs 1-shot'] = (self.summary['VWAP Price'] - self.summary['1-shot Price']) * self.summary['Base Amount Transacted']
        if self.config.is_buy:
            self.summary['P&L vs 1-shot'] *= -1

        # End the bot if the remaining amount is below the minimum
        if self.remaining_amount_quote <= self.minimum_amount_quote:
            for key, value in self.summary.items():
                self.notify_hb_app(f"{key}: {str(round(value, 4))}")
            HummingbotApplication.main_application().stop()
        else:
            self.waiting_for_fill = False
            self.delay_timestamp = self.current_timestamp + self.config.filled_order_delay

    # This method overrides the format_status in ScriptStrategyBase to include VWAP information
    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        # Balances table
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        # Fills table
        fills_df = pd.DataFrame(self.fills)
        lines.extend(["", "  Fills:"] + ["    " + line for line in fills_df.to_string(index=False).split("\n")])

        # VWAP Summary table
        summary_df = pd.DataFrame(list(self.summary.items()), columns=['Key', 'Value'])
        summary_df['Value'] = summary_df['Value'].apply(lambda x: round(x, 4) if isinstance(x, (int, float, Decimal)) else x)
        lines.extend(["", "  Summary:"] + ["    " + line for line in summary_df.to_string(index=False).split("\n")])
        lines.extend(["", f"  Next order in: {self.delay_timestamp - self.current_timestamp:.0f} seconds"])

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
