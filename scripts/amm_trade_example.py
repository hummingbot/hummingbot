import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DEXTradeConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("jupiter/router", json_schema_extra={
        "prompt": "DEX connector in format 'name/type' (e.g., jupiter/router, uniswap/amm)", "prompt_on_new": True})
    trading_pair: str = Field("SOL-USDC", json_schema_extra={
        "prompt": "Trading pair (e.g. SOL-USDC)", "prompt_on_new": True})
    target_price: Decimal = Field(Decimal("142"), json_schema_extra={
        "prompt": "Target price to trigger trade", "prompt_on_new": True})
    trigger_above: bool = Field(False, json_schema_extra={
        "prompt": "Trigger when price rises above target? (True for above/False for below)", "prompt_on_new": True})
    is_buy: bool = Field(True, json_schema_extra={
        "prompt": "Buying or selling the base asset? (True for buy, False for sell)", "prompt_on_new": True})
    amount: Decimal = Field(Decimal("0.01"), json_schema_extra={
        "prompt": "Order amount (in base token)", "prompt_on_new": True})
    check_interval: int = Field(10, json_schema_extra={
        "prompt": "How often to check price in seconds (default: 10)", "prompt_on_new": False})


class DEXTrade(ScriptStrategyBase):
    """
    This strategy monitors DEX prices and executes a swap when a price threshold is reached.
    """

    @classmethod
    def init_markets(cls, config: DEXTradeConfig):
        # New gateway connector format: name/type (e.g., jupiter/router, uniswap/amm)
        cls.markets = {config.connector: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DEXTradeConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = config.connector  # Now in format name/type
        self.base, self.quote = self.config.trading_pair.split("-")

        # State tracking
        self.trade_executed = False
        self.trade_in_progress = False
        self.last_price = None
        self.last_price_update = None
        self.last_check_time = None

        # Balance tracking
        self.initial_base_balance = None
        self.initial_quote_balance = None
        self.final_base_balance = None
        self.final_quote_balance = None
        self.order_id = None
        self.balance_check_delay = 2  # seconds to wait after fill before checking balances

        # Log trade information
        condition = "rises above" if self.config.trigger_above else "falls below"
        side = "BUY" if self.config.is_buy else "SELL"
        self.log_with_clock(logging.INFO, f"Will {side} {self.config.amount} {self.base} for {self.quote} on {self.exchange} when price {condition} {self.config.target_price}")
        self.log_with_clock(logging.INFO, f"Price will be checked every {self.config.check_interval} seconds")

    async def check_price_and_trade(self):
        """Check current price and trigger trade if condition is met"""
        if self.trade_in_progress or self.trade_executed:
            return

        self.trade_in_progress = True
        current_price = None  # Initialize current_price

        side = "buy" if self.config.is_buy else "sell"
        msg = (f"Getting quote on {self.config.connector} "
               f"to {side} {self.config.amount} {self.base} "
               f"for {self.quote}")

        try:
            self.log_with_clock(logging.INFO, msg)
            current_price = await self.connectors[self.exchange].get_quote_price(
                trading_pair=self.config.trading_pair,
                is_buy=self.config.is_buy,
                amount=self.config.amount,
            )

            # Update last price tracking
            self.last_price = current_price
            self.last_price_update = datetime.now()

            # Log current price vs target
            price_diff = current_price - self.config.target_price
            percentage_diff = (price_diff / self.config.target_price) * 100

            if self.config.trigger_above:
                status = "waiting for price to rise" if current_price < self.config.target_price else "ABOVE TARGET"
                self.log_with_clock(logging.INFO,
                                    f"Current price: {current_price:.6f} | Target: {self.config.target_price:.6f} | "
                                    f"Difference: {price_diff:.6f} ({percentage_diff:+.2f}%) | Status: {status}")
            else:
                status = "waiting for price to fall" if current_price > self.config.target_price else "BELOW TARGET"
                self.log_with_clock(logging.INFO,
                                    f"Current price: {current_price:.6f} | Target: {self.config.target_price:.6f} | "
                                    f"Difference: {price_diff:.6f} ({percentage_diff:+.2f}%) | Status: {status}")

        except Exception as e:
            self.log_with_clock(logging.ERROR, f"Error getting quote: {e}")
            self.trade_in_progress = False
            return  # Exit if we couldn't get the price

        # Continue with rest of the function only if we have a valid price
        if current_price is not None:
            # Check if price condition is met
            condition_met = False
            if self.config.trigger_above and current_price > self.config.target_price:
                condition_met = True
                self.log_with_clock(logging.INFO, f"Price rose above target: {current_price} > {self.config.target_price}")
            elif not self.config.trigger_above and current_price < self.config.target_price:
                condition_met = True
                self.log_with_clock(logging.INFO, f"Price fell below target: {current_price} < {self.config.target_price}")

            if condition_met:
                try:
                    self.log_with_clock(logging.INFO, "Price condition met! Submitting trade...")

                    # Record initial balances before trade
                    connector = self.connectors[self.exchange]
                    self.initial_base_balance = connector.get_balance(self.base)
                    self.initial_quote_balance = connector.get_balance(self.quote)

                    self.order_id = connector.place_order(
                        is_buy=self.config.is_buy,
                        trading_pair=self.config.trading_pair,
                        amount=self.config.amount,
                        price=current_price,
                    )
                    self.log_with_clock(logging.INFO, f"Trade order submitted with ID: {self.order_id} (awaiting execution)")
                    self.trade_executed = True
                except Exception as e:
                    self.log_with_clock(logging.ERROR, f"Error submitting trade: {str(e)}")
                finally:
                    if not self.trade_executed:
                        self.trade_in_progress = False
            else:
                # Price condition not met, reset flag to allow next check
                self.trade_in_progress = False

    def on_tick(self):
        # Don't check price if trade already executed or in progress
        if self.trade_executed or self.trade_in_progress:
            return

        # Check if enough time has passed since last check
        current_time = datetime.now()
        if self.last_check_time is None or (current_time - self.last_check_time).total_seconds() >= self.config.check_interval:
            self.last_check_time = current_time
            safe_ensure_future(self.check_price_and_trade())

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Called when an order is filled. Capture final balances after trade execution.
        """
        if event.order_id == self.order_id:
            self.log_with_clock(logging.INFO, f"Order {event.order_id} filled! Fetching updated balances...")
            # Schedule balance check after a short delay to ensure balances are updated
            safe_ensure_future(self._fetch_final_balances())

    async def _fetch_final_balances(self):
        """
        Fetch final balances after a short delay to ensure they're updated.
        """
        import asyncio
        await asyncio.sleep(self.balance_check_delay)

        connector = self.connectors[self.exchange]

        # Force a balance update to get fresh balances
        await connector.update_balances(on_interval=False)

        # Now get the updated balances
        self.final_base_balance = connector.get_balance(self.base)
        self.final_quote_balance = connector.get_balance(self.quote)

        # Log the actual balance values for debugging
        self.log_with_clock(logging.INFO,
                            f"Initial balances - {self.base}: {self.initial_base_balance:.6f}, {self.quote}: {self.initial_quote_balance:.6f}")
        self.log_with_clock(logging.INFO,
                            f"Final balances - {self.base}: {self.final_base_balance:.6f}, {self.quote}: {self.final_quote_balance:.6f}")

        # Log balance changes
        base_change = self.final_base_balance - self.initial_base_balance
        quote_change = self.final_quote_balance - self.initial_quote_balance

        self.log_with_clock(logging.INFO, f"Balance changes - {self.base}: {base_change:+.6f}, {self.quote}: {quote_change:+.6f}")

        # Notify user of trade completion with balance changes
        side = "Bought" if self.config.is_buy else "Sold"
        msg = f"{side} {self.config.amount} {self.base}. Balance changes: {self.base} {base_change:+.6f}, {self.quote} {quote_change:+.6f}"
        self.notify_hb_app_with_timestamp(msg)

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if self.trade_executed:
            lines = []
            lines.append(f"Exchange: {self.config.connector}")
            lines.append(f"Pair: {self.base}-{self.quote}")
            side = "BUY" if self.config.is_buy else "SELL"
            lines.append(f"Action: {side} {self.config.amount} {self.base}")

            # Show balance changes if available
            if self.initial_base_balance is not None and self.final_base_balance is not None:
                base_change = self.final_base_balance - self.initial_base_balance
                quote_change = self.final_quote_balance - self.initial_quote_balance
                # Trade summary
                lines.append("\nTrade Summary:")
                if self.config.is_buy:
                    lines.append(f"  Bought {base_change:+.6f} {self.base}")
                    lines.append(f"  Spent {-quote_change:.6f} {self.quote}")
                    if base_change != 0:
                        avg_price = abs(quote_change / base_change)
                        lines.append(f"  Price: {avg_price:.6f} {self.quote}/{self.base}")
                else:
                    lines.append(f"  Sold {-base_change:.6f} {self.base}")
                    lines.append(f"  Received {quote_change:+.6f} {self.quote}")
                    if base_change != 0:
                        avg_price = abs(quote_change / base_change)
                        lines.append(f"  Price: {avg_price:.6f} {self.quote}/{self.base}")

            return "\n".join(lines)

        lines = []
        side = "buy" if self.config.is_buy else "sell"
        condition = "rises above" if self.config.trigger_above else "falls below"

        lines.append(f"Exchange: {self.config.connector}")
        lines.append(f"Pair: {self.base}-{self.quote}")
        lines.append(f"Action: {side.upper()} {self.config.amount} {self.base} when price {condition} {self.config.target_price}")
        lines.append(f"Check Interval: Every {self.config.check_interval} seconds")

        if self.trade_in_progress:
            lines.append("\nStatus: 🔄 Currently checking price...")
        elif self.last_price is not None:
            # Calculate price difference
            price_diff = self.last_price - self.config.target_price
            percentage_diff = (price_diff / self.config.target_price) * 100

            # Determine status
            if self.config.trigger_above:
                if self.last_price < self.config.target_price:
                    status_emoji = "⏳"
                    status_text = f"Waiting (need {self.config.target_price - self.last_price:.6f} more)"
                else:
                    status_emoji = "✅"
                    status_text = "READY TO TRADE"
            else:
                if self.last_price > self.config.target_price:
                    status_emoji = "⏳"
                    status_text = f"Waiting (need {self.last_price - self.config.target_price:.6f} drop)"
                else:
                    status_emoji = "✅"
                    status_text = "READY TO TRADE"

            lines.append(f"\nCurrent Price: {self.last_price:.6f} {self.quote}")
            lines.append(f"Target Price:  {self.config.target_price:.6f} {self.quote}")
            lines.append(f"Difference:    {price_diff:.6f} ({percentage_diff:+.2f}%)")
            lines.append(f"Status:        {status_emoji} {status_text}")

            if self.last_price_update:
                seconds_ago = (datetime.now() - self.last_price_update).total_seconds()
                lines.append(f"\nLast update: {int(seconds_ago)}s ago")

            # Show next check time
            if self.last_check_time:
                next_check_in = self.config.check_interval - int((datetime.now() - self.last_check_time).total_seconds())
                if next_check_in > 0:
                    lines.append(f"Next check in: {next_check_in}s")
        else:
            lines.append("\nStatus: ⏳ Waiting for first price update...")

        return "\n".join(lines)
