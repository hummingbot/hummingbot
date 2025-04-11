import logging
import os
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

        # Log trade information
        condition = "rises above" if self.config.trigger_above else "falls below"
        side = "BUY" if self.config.is_buy else "SELL"
        self.log_with_clock(logging.INFO, f"Will {side} {self.config.amount} {self.base} for {self.quote} on {self.exchange} when price {condition} {self.config.target_price}")

    def on_tick(self):
        # Don't check price if trade already executed or in progress
        if self.trade_executed or self.trade_in_progress:
            return

        # Check price on each tick
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
            self.log_with_clock(logging.INFO, f"Price: {current_price}")
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

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if self.trade_executed:
            return "Trade has been executed successfully!"

        if self.trade_in_progress:
            return "Currently checking price or executing trade..."

        condition = "rises above" if self.config.trigger_above else "falls below"

        lines = []
        side = "buy" if self.config.is_buy else "sell"
        connector_chain_network = f"{self.config.connector}_{self.config.chain}_{self.config.network}"
        lines.append(f"Monitoring {self.base}-{self.quote} price on {connector_chain_network}")
        lines.append(f"Will execute {side} trade when price {condition} {self.config.target_price}")
        lines.append(f"Trade amount: {self.config.amount} {self.base}")
        lines.append("Checking price on every tick")

        return "\n".join(lines)
