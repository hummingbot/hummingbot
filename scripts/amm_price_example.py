import logging
import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DEXPriceConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("jupiter", json_schema_extra={
        "prompt": "DEX to swap on", "prompt_on_new": True})
    chain: str = Field("solana", json_schema_extra={
        "prompt": "Chain", "prompt_on_new": True})
    network: str = Field("mainnet-beta", json_schema_extra={
        "prompt": "Network", "prompt_on_new": True})
    trading_pair: str = Field("SOL-USDC", json_schema_extra={
        "prompt": "Trading pair in which the bot will place orders", "prompt_on_new": True})
    is_buy: bool = Field(True, json_schema_extra={
        "prompt": "Buying or selling the base asset? (True for buy, False for sell)", "prompt_on_new": True})
    amount: Decimal = Field(Decimal("0.01"), json_schema_extra={
        "prompt": "Amount of base asset to buy or sell", "prompt_on_new": True})


class DEXPrice(ScriptStrategyBase):
    """
    This example shows how to use the GatewaySwap connector to fetch price for a swap
    """

    @classmethod
    def init_markets(cls, config: DEXPriceConfig):
        connector_chain_network = f"{config.connector}_{config.chain}_{config.network}"
        cls.markets = {connector_chain_network: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DEXPriceConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange = f"{config.connector}_{config.chain}_{config.network}"
        self.base, self.quote = self.config.trading_pair.split("-")

    def on_tick(self):
        # wrap async task in safe_ensure_future
        safe_ensure_future(self.async_task())

    # async task since we are using Gateway
    async def async_task(self):
        # fetch price using GatewaySwap instead of direct HTTP call
        side = "buy" if self.config.is_buy else "sell"
        msg = (f"Getting quote on {self.exchange} "
               f"to {side} {self.config.amount} {self.base} "
               f"for {self.quote}")
        try:
            self.log_with_clock(logging.INFO, msg)
            price = await self.connectors[self.exchange].get_quote_price(
                trading_pair=self.config.trading_pair,
                is_buy=self.config.is_buy,
                amount=self.config.amount,
            )
            self.log_with_clock(logging.INFO, f"Price: {price}")
        except Exception as e:
            self.log_with_clock(logging.ERROR, f"Error getting quote: {e}")
