import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DEXTradeConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("jupiter", json_schema_extra={
        "prompt": "Connector name (e.g. jupiter, uniswap)", "prompt_on_new": True})
    chain: str = Field("solana", json_schema_extra={
        "prompt": "Chain (e.g. solana, ethereum)", "prompt_on_new": True})
    network: str = Field("mainnet-beta", json_schema_extra={
        "prompt": "Network (e.g. mainnet-beta (solana), base (ethereum))", "prompt_on_new": True})
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
        connector_chain_network = f"{config.connector}_{config.chain}_{config.network}"
        cls.markets = {connector_chain_network: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DEXTradeConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = f"{config.connector}_{config.chain}_{config.network}"
        self.base, self.quote = self.config.trading_pair.split("-")

        # State tracking
        self.trade_executed = False
        self.trade_in_progress = False
        self.last_price = None
        self.last_price_update = None
        self.last_check_time = None

        # Log trade information
        condition = "rises above" if self.config.trigger_above else "falls below"
        side = "BUY" if self.config.is_buy else "SELL"
        self.log_with_clock(logging.INFO, f"Will {side} {self.config.amount} {self.base} for {self.quote} on {self.exchange} when price {condition} {self.config.target_price}")
        self.log_with_clock(logging.INFO, f"Price will be checked every {self.config.check_interval} seconds")

    def on_tick(self):
        # Don't check price if trade already executed or in progress
        if self.trade_executed or self.trade_in_progress:
            return

        # Check if enough time has passed since last check
        current_time = datetime.now()
        if self.last_check_time is None or (current_time - self.last_check_time).total_seconds() >= self.config.check_interval:
            self.last_check_time = current_time
            safe_ensure_future(self.check_price_and_trade())

    async def check_price_and_trade(self):
        """Check current price and trigger trade if condition is met"""
        if self.trade_in_progress or self.trade_executed:
            return

        self.trade_in_progress = True
        current_price = None  # Initialize current_price

        side = "buy" if self.config.is_buy else "sell"
        msg = (f"Getting quote on {self.config.connector} "
               f"({self.config.chain}/{self.config.network}) "
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
                    self.log_with_clock(logging.INFO, "Price condition met! Executing trade...")

                    order_id = self.connectors[self.exchange].place_order(
                        is_buy=self.config.is_buy,
                        trading_pair=self.config.trading_pair,
                        amount=self.config.amount,
                        price=current_price,
                    )
                    self.log_with_clock(logging.INFO, f"Trade executed with order ID: {order_id}")
                    self.trade_executed = True
                except Exception as e:
                    self.log_with_clock(logging.ERROR, f"Error executing trade: {str(e)}")
                finally:
                    if not self.trade_executed:
                        self.trade_in_progress = False
            else:
                # Price condition not met, reset flag to allow next check
                self.trade_in_progress = False

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if self.trade_executed:
            return "Trade has been executed successfully!"

        lines = []
        side = "buy" if self.config.is_buy else "sell"
        connector_chain_network = f"{self.config.connector}_{self.config.chain}_{self.config.network}"
        condition = "rises above" if self.config.trigger_above else "falls below"

        lines.append("=== DEX Trade Monitor ===")
        lines.append(f"Exchange: {connector_chain_network}")
        lines.append(f"Pair: {self.base}-{self.quote}")
        lines.append(f"Strategy: {side.upper()} {self.config.amount} {self.base} when price {condition} {self.config.target_price}")
        lines.append(f"Check interval: Every {self.config.check_interval} seconds")

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
