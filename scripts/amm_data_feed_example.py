import os
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

        # Start the data feed
        self.amm_data_feed.start()

    async def on_stop(self):
        self.amm_data_feed.stop()

    def on_tick(self):
        pass

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
            rows.extend(dict(price) for token, price in self.amm_data_feed.price_dict.items())
            if rows:
                df = pd.DataFrame(rows)
                prices_str = format_df_for_printout(df, table_format="psql")
                lines.append(f"AMM Data Feed is ready.\n{prices_str}")

            # Show which pairs failed to fetch data
            if pairs_without_data:
                lines.append(f"\nFailed to fetch data for: {', '.join(sorted(pairs_without_data))}")
        else:
            lines.append("AMM Data Feed is not ready.")
            lines.append(f"Configured pairs: {', '.join(sorted(configured_pairs))}")
            lines.append("Waiting for price data...")

        return "\n".join(lines)
