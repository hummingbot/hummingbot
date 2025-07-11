import logging
import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AmmPriceConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field(
        "minswap/amm",
        json_schema_extra={"prompt": "Gateway connector ID (e.g. minswap/amm)", "prompt_on_new": True}
    )
    chain: str = Field(
        "cardano",
        json_schema_extra={"prompt": "Chain (e.g. cardano)", "prompt_on_new": True}
    )
    network: str = Field(
        "preprod",
        json_schema_extra={"prompt": "Network (e.g. preprod)", "prompt_on_new": True}
    )
    trading_pair: str = Field(
        "ADA-MIN",
        json_schema_extra={"prompt": "Trading pair (e.g. ADA-MIN)", "prompt_on_new": True}
    )
    side: str = Field(
        "SELL",
        json_schema_extra={"prompt": "Trade side (BUY or SELL)", "prompt_on_new": True}
    )
    amount: Decimal = Field(
        Decimal("0.01"),
        json_schema_extra={"prompt": "Amount of quote asset to trade", "prompt_on_new": True}
    )


class AmmPriceMinswap(ScriptStrategyBase):
    """
    Fetches a single price quote from Minswap AMM via the Gateway HTTP API.
    """

    @classmethod
    def init_markets(cls, config: AmmPriceConfig):
        # No on‑chain markets → skip readiness polling
        cls.markets = {}

    def __init__(self, connectors: Dict[str, object], config: AmmPriceConfig):
        super().__init__(connectors)
        self.config = config
        self.base, self.quote = config.trading_pair.split("-")
        # Map to the enum the HTTP client expects:
        self.trade_type = TradeType.BUY if config.side.upper() == "BUY" else TradeType.SELL
        self.has_fetched = False  # Flag to track if we've already fetched
        self.logger().info(
            f"Initialized AmmPriceMinswap: "
            f"{config.connector}/{config.chain}/{config.network} "
            f"pair={config.trading_pair} side={config.side} amount={config.amount}"
        )

    def on_tick(self):
        # Only fetch once
        if not self.has_fetched:
            self.has_fetched = True
            safe_ensure_future(self.async_fetch())

    async def async_fetch(self):
        try:
            self.log_with_clock(
                logging.INFO,
                f"Fetching {self.config.side.upper()} quote for {self.config.trading_pair} "
                f"amount={self.config.amount}"
            )

            # *** Use positional args so nothing shifts: ***
            data = await GatewayHttpClient.get_instance().get_price(
                # 1) chain
                self.config.chain,
                # 2) network
                self.config.network,
                # 3) connector
                self.config.connector,
                # 4) base token symbol
                self.base,
                # 5) quote token symbol
                self.quote,
                # 6) amount of quote asset
                self.config.amount,
                # 7) side (TradeType)
                self.trade_type,
            )

            # Extract all available data from the response
            pool_address = data.get("poolAddress", "N/A")
            estimated_amount_in = data.get("estimatedAmountIn", "N/A")
            estimated_amount_out = data.get("estimatedAmountOut", "N/A")
            min_amount_out = data.get("minAmountOut", "N/A")
            max_amount_in = data.get("maxAmountIn", "N/A")
            base_token_balance_change = data.get("baseTokenBalanceChange", "N/A")
            quote_token_balance_change = data.get("quoteTokenBalanceChange", "N/A")
            price = data.get("price", "N/A")

            # Log comprehensive quote information
            self.log_with_clock(
                logging.INFO,
                "=== MINSWAP AMM QUOTE DETAILS ==="
            )
            self.log_with_clock(
                logging.INFO,
                f"Pool Address: {pool_address}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Estimated Amount In: {estimated_amount_in} {self.quote if self.config.side.upper() == 'SELL' else self.base}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Estimated Amount Out: {estimated_amount_out} {self.base if self.config.side.upper() == 'SELL' else self.quote}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Min Amount Out (with slippage): {min_amount_out}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Max Amount In (with slippage): {max_amount_in}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Base Token Balance Change: {base_token_balance_change} {self.base}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Quote Token Balance Change: {quote_token_balance_change} {self.quote}"
            )
            self.log_with_clock(
                logging.INFO,
                f"Price: {price}"
            )

            # Log completion message
            self.log_with_clock(
                logging.INFO,
                "Price fetch completed. Script will not fetch again."
            )

        except Exception as e:
            self.log_with_clock(
                logging.ERROR,
                f"Error fetching quote from Minswap AMM: {e}"
            )
