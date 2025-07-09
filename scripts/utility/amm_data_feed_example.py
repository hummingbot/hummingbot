import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.amm_gateway_data_feed import AmmGatewayDataFeed
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AMMDataFeedConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("jupiter", json_schema_extra={
        "prompt": "DEX connector name", "prompt_on_new": True})
    chain: str = Field("solana", json_schema_extra={
        "prompt": "Chain", "prompt_on_new": True})
    network: str = Field("mainnet-beta", json_schema_extra={
        "prompt": "Network", "prompt_on_new": True})
    order_amount_in_base: Decimal = Field(Decimal("1.0"), json_schema_extra={
        "prompt": "Order amount in base currency", "prompt_on_new": True})
    trading_pair_1: str = Field("SOL-USDC", json_schema_extra={
        "prompt": "First trading pair", "prompt_on_new": True})
    trading_pair_2: Optional[str] = Field(None, json_schema_extra={
        "prompt": "Second trading pair (optional)", "prompt_on_new": False})
    trading_pair_3: Optional[str] = Field(None, json_schema_extra={
        "prompt": "Third trading pair (optional)", "prompt_on_new": False})
    file_name: Optional[str] = Field(None, json_schema_extra={
        "prompt": "Output file name (without extension, defaults to connector_chain_network_timestamp)",
        "prompt_on_new": False})


class AMMDataFeedExample(ScriptStrategyBase):
    """
    This example shows how to use the AmmGatewayDataFeed to fetch prices from a DEX
    """

    @classmethod
    def init_markets(cls, config: AMMDataFeedConfig):
        # Gateway connectors don't need market initialization
        cls.markets = {}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: AMMDataFeedConfig):
        super().__init__(connectors)
        self.config = config
        self.price_history = []
        self.last_save_time = datetime.now()
        self.save_interval = 60  # Save every 60 seconds

        # Build trading pairs set
        trading_pairs = {config.trading_pair_1}
        if config.trading_pair_2:
            trading_pairs.add(config.trading_pair_2)
        if config.trading_pair_3:
            trading_pairs.add(config.trading_pair_3)

        # Create connector chain network string
        connector_chain_network = f"{config.connector}_{config.chain}_{config.network}"

        # Initialize the AMM data feed
        self.amm_data_feed = AmmGatewayDataFeed(
            connector_chain_network=connector_chain_network,
            trading_pairs=trading_pairs,
            order_amount_in_base=config.order_amount_in_base,
        )

        # Create data directory if it doesn't exist
        # Use hummingbot root directory (2 levels up from scripts/)
        hummingbot_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(hummingbot_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)

        # Set file name
        if config.file_name:
            self.file_name = f"{config.file_name}.csv"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.file_name = f"{connector_chain_network}_{timestamp}.csv"

        self.file_path = os.path.join(self.data_dir, self.file_name)
        self.logger().info(f"Data will be saved to: {self.file_path}")

        # Start the data feed
        self.amm_data_feed.start()

    async def on_stop(self):
        self.amm_data_feed.stop()
        # Save any remaining data before stopping
        self._save_data_to_csv()

    def on_tick(self):
        # Collect price data if available
        if self.amm_data_feed.is_ready() and self.amm_data_feed.price_dict:
            timestamp = datetime.now()
            for trading_pair, price_info in self.amm_data_feed.price_dict.items():
                data_row = {
                    "timestamp": timestamp,
                    "trading_pair": trading_pair,
                    "buy_price": float(price_info.buy_price),
                    "sell_price": float(price_info.sell_price),
                    "mid_price": float((price_info.buy_price + price_info.sell_price) / 2)
                }
                self.price_history.append(data_row)

            # Save data periodically
            if (timestamp - self.last_save_time).total_seconds() >= self.save_interval:
                self._save_data_to_csv()
                self.last_save_time = timestamp

    def _save_data_to_csv(self):
        """Save collected price data to CSV file"""
        if not self.price_history:
            return

        df = pd.DataFrame(self.price_history)

        # Check if file exists to determine whether to write header
        file_exists = os.path.exists(self.file_path)

        # Append to existing file or create new one
        df.to_csv(self.file_path, mode='a', header=not file_exists, index=False)

        self.logger().info(f"Saved {len(self.price_history)} price records to {self.file_path}")

        # Clear history after saving
        self.price_history = []

    def format_status(self) -> str:
        lines = []

        # Get all configured trading pairs
        configured_pairs = {self.config.trading_pair_1}
        if self.config.trading_pair_2:
            configured_pairs.add(self.config.trading_pair_2)
        if self.config.trading_pair_3:
            configured_pairs.add(self.config.trading_pair_3)

        # Check which pairs have data
        pairs_with_data = set(self.amm_data_feed.price_dict.keys())
        pairs_without_data = configured_pairs - pairs_with_data

        if self.amm_data_feed.is_ready():
            # Show price data for pairs that have it
            rows = []
            for token, price in self.amm_data_feed.price_dict.items():
                rows.append({
                    "trading_pair": token,
                    "buy_price": float(price.buy_price),
                    "sell_price": float(price.sell_price),
                    "mid_price": float((price.buy_price + price.sell_price) / 2)
                })
            if rows:
                df = pd.DataFrame(rows)
                prices_str = format_df_for_printout(df, table_format="psql")
                lines.append(f"AMM Data Feed is ready.\n{prices_str}")

            # Show which pairs failed to fetch data
            if pairs_without_data:
                lines.append(f"\nFailed to fetch data for: {', '.join(sorted(pairs_without_data))}")

            # Add data collection status
            lines.append("\nData collection status:")
            lines.append(f"  Output file: {self.file_path}")
            lines.append(f"  Records in buffer: {len(self.price_history)}")
            lines.append(f"  Save interval: {self.save_interval} seconds")
            lines.append(f"  Next save in: {self.save_interval - int((datetime.now() - self.last_save_time).total_seconds())} seconds")
        else:
            lines.append("AMM Data Feed is not ready.")
            lines.append(f"Configured pairs: {', '.join(sorted(configured_pairs))}")
            lines.append("Waiting for price data...")

        return "\n".join(lines)
