from decimal import Decimal
from typing import Dict

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.amm_gateway_data_feed import AmmGatewayDataFeed
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AMMDataFeedExample(ScriptStrategyBase):
    amm_data_feed_uniswap = AmmGatewayDataFeed(
        connector_chain_network="uniswap_polygon_mainnet",
        trading_pairs={"LINK-USDC", "AAVE-USDC", "WMATIC-USDT"},
        order_amount_in_base=Decimal("1"),
    )
    amm_data_feed_quickswap = AmmGatewayDataFeed(
        connector_chain_network="quickswap_polygon_mainnet",
        trading_pairs={"LINK-USDC", "AAVE-USDC", "WMATIC-USDT"},
        order_amount_in_base=Decimal("1"),
    )
    markets = {"binance_paper_trade": {"BTC-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.amm_data_feed_uniswap.start()
        self.amm_data_feed_quickswap.start()

    async def on_stop(self):
        self.amm_data_feed_uniswap.stop()
        self.amm_data_feed_quickswap.stop()

    def on_tick(self):
        pass

    def format_status(self) -> str:
        if self.amm_data_feed_uniswap.is_ready() and self.amm_data_feed_quickswap.is_ready():
            lines = []
            rows = []
            rows.extend(dict(price) for token, price in self.amm_data_feed_uniswap.price_dict.items())
            rows.extend(dict(price) for token, price in self.amm_data_feed_quickswap.price_dict.items())
            df = pd.DataFrame(rows)
            prices_str = format_df_for_printout(df, table_format="psql")
            lines.append(f"AMM Data Feed is ready.\n{prices_str}")
            return "\n".join(lines)
        else:
            return "AMM Data Feed is not ready."
