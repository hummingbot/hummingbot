import asyncio
import logging
import os
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Literal, Optional

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class LiquidityBotConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field(
        "minswap/amm",
        json_schema_extra={"prompt": "Gateway connector ID (e.g. minswap/amm)", "prompt_on_new": True},
    )
    chain: str = Field(
        "cardano",
        json_schema_extra={"prompt": "Chain (e.g. cardano)", "prompt_on_new": True},
    )
    network: str = Field(
        "preprod",
        json_schema_extra={"prompt": "Network (e.g. preprod)", "prompt_on_new": True},
    )
    trading_pair: str = Field(
        "ADA-MIN",
        json_schema_extra={"prompt": "Trading pair (e.g. ADA-MIN)", "prompt_on_new": True},
    )
    side: Literal["ADD", "REMOVE"] = Field(
        "ADD",
        json_schema_extra={"prompt": "Liquidity side (ADD or REMOVE)", "prompt_on_new": True},
    )
    base_amount: Optional[Decimal] = Field(
        Decimal("10"),
        json_schema_extra={
            "prompt": lambda config: (
                "Base amount for the Liquidity Action"
                if config and config.side == "ADD"
                else None
            ),
            "prompt_on_new": True,
        },
    )

    decrease_percentage: Optional[Decimal] = Field(
        None,
        json_schema_extra={
            "prompt": lambda config: (
                "Decrease percentage for REMOVE liquidity (0 < value < 100)"
                if config and config.side == "REMOVE"
                else None
            ),
            "prompt_on_new": True,
        },
        gt=0,
        lt=100
    )


class LiquidityBot(ScriptStrategyBase):
    """
    A script strategy to perform a one-time ADD or REMOVE liquidity operation via the Gateway.
    """

    @classmethod
    def init_markets(cls, config: LiquidityBotConfig):
        # Since we're using Gateway HTTP client directly, we don't need to initialize markets
        # Just set an empty markets dict to avoid the connector lookup error
        cls.markets = {}

    def __init__(self, connectors, config: LiquidityBotConfig):
        super().__init__(connectors)
        self.config = config
        self._task_running = False
        self._executed = False
        self._wallet_address = None
        self._logger = logging.getLogger(__name__)
        self.trade_start_time = None

    def markets_ready(self):
        # Override the default markets_ready check since we're using Gateway HTTP client directly
        # and don't need to wait for traditional connectors to be ready
        return True

    def on_tick(self):
        # Launch the async task once
        if not self._task_running and not self._executed:
            self._task_running = True
            self.trade_start_time = datetime.now()
            safe_ensure_future(self._async_task())

    async def _async_task(self):  # type: ignore
        try:
            connector = self.config.connector
            chain = self.config.chain
            network = self.config.network
            # Parse the base and quote tokens
            token0, token1 = self.config.trading_pair.split("-")

            # Load wallet address
            gateways = GatewayConnectionSetting.load()
            wallet = next(
                (w for w in gateways if w["connector"] == connector
                    and w["chain"] == chain
                    and w["network"] == network),
                None,
            )
            if wallet is None:
                raise ValueError(f"No gateway connection for {connector} on {chain}-{network}")
            address = wallet["wallet_address"]
            # Get initial balances
            await self.get_balance(address, [token0, token1])

            if self.config.side == "ADD":
                # Quote the second token amount
                price_data = await GatewayHttpClient.get_instance().pool_info(
                    connector,
                    network,
                    base_token=token0,
                    quote_token=token1
                )
                price = Decimal(price_data["price"])
                base_amount = self.config.base_amount
                quote_amount = (base_amount / price).quantize(Decimal("1."), rounding=ROUND_DOWN)
                self._logger.info(f"Adding liquidity: {base_amount} {token0}, {quote_amount} {token1}")

                res = await GatewayHttpClient.get_instance().amm_add_liquidity(
                    connector=connector,
                    network=network,
                    wallet_address=address,
                    base_token_amount=float(base_amount),
                    quote_token_amount=float(quote_amount),
                    base_token=token0,
                    quote_token=token1
                )

                tx_hash = res.get("signature")

            else:  # REMOVE
                pct = self.config.decrease_percentage
                if pct is None:
                    raise ValueError("decrease_percentage is required for REMOVE side")
                self._logger.info(f"Removing {pct}% liquidity on {self.config.trading_pair}")
                res = await GatewayHttpClient.get_instance().amm_remove_liquidity(
                    connector=connector,
                    network=network,
                    wallet_address=address,
                    percentage=float(pct),
                    base_token=token0,
                    quote_token=token1
                )
                tx_hash = res.get("signature")

            if not tx_hash:
                raise RuntimeError("Transaction submission failed: no txHash returned")

            self._logger.info(f"Submitted tx {tx_hash}, polling for confirmation...")
            await self.poll_transaction(tx_hash)
            self._logger.info("Liquidity operation confirmed.")
            self._executed = True
        except Exception as e:
            self._logger.error(f"Error during liquidity operation: {e}")
        finally:
            self._task_running = False

    async def poll_transaction(self, tx_hash: str):
        try:
            self.log_with_clock(logging.INFO, f"Polling transaction status for {tx_hash}...")
            start_time = datetime.now()
            timeout = 300  # 5 minutes timeout

            while (datetime.now() - start_time).total_seconds() < timeout:
                try:
                    poll_data = await GatewayHttpClient.get_instance().get_transaction_status(
                        chain=self.config.chain,
                        network=self.config.network,
                        transaction_hash=tx_hash
                    )

                    # Parse the response according to the actual structure
                    tx_status = poll_data.get("txStatus", -1)
                    tx_data = poll_data.get("txData", {})

                    # Status codes (assuming): 0 = pending, 1 = confirmed, others = failed
                    if tx_status == 1:  # Confirmed
                        self.log_with_clock(logging.INFO, "Transaction confirmed successfully!")
                        self.log_with_clock(logging.INFO, f"Block: {tx_data.get('block')}")
                        self.log_with_clock(logging.INFO, f"Block Height: {tx_data.get('blockHeight')}")
                        self.log_with_clock(logging.INFO, f"Fees: {poll_data.get('fee', 'N/A')} lovelace")
                        self.log_with_clock(logging.INFO, f"Block Time: {tx_data.get('blockTime', 'N/A')}")
                        if tx_data.get('validContract', False):
                            self.log_with_clock(logging.INFO, "Contract execution was valid")
                        else:
                            self.log_with_clock(logging.WARNING, "Contract execution was invalid")
                        return
                    elif tx_status == 0:  # Pending
                        current_block = poll_data.get("currentBlock")
                        tx_block = poll_data.get("txBlock")

                        # Handle None values safely
                        if current_block is None or tx_block is None:
                            self.log_with_clock(logging.INFO, "Transaction pending (waiting for block information)...")
                        else:
                            try:
                                blocks_remaining = max(0, tx_block - current_block) if tx_block > current_block else 0
                                self.log_with_clock(logging.INFO,
                                                    f"Transaction pending. Current block: {current_block}, "
                                                    f"Transaction block: {tx_block}, "
                                                    f"Blocks remaining: {blocks_remaining}")
                            except TypeError:
                                self.log_with_clock(logging.INFO, "Transaction pending (waiting for valid block numbers)...")
                    else:  # Failed or unknown status
                        self.log_with_clock(logging.ERROR, f"Transaction failed with status: {tx_status}")
                        return

                    await asyncio.sleep(10)  # Wait 10 seconds between polls

                except Exception as poll_error:
                    self.log_with_clock(logging.ERROR, f"Polling error: {str(poll_error)}", exc_info=True)
                    await asyncio.sleep(5)  # Shorter wait if error occurred

            self.log_with_clock(logging.ERROR, "Transaction polling timed out after 5 minutes")

        except Exception as e:
            self.log_with_clock(logging.ERROR, f"Error in transaction polling: {str(e)}", exc_info=True)

    async def get_balance(self, address: str, tokens: list):
        try:
            self.log_with_clock(logging.INFO, f"Fetching balances for {address}...")
            balance_data = await GatewayHttpClient.get_instance().get_balances(
                self.config.chain,
                self.config.network,
                address,
                tokens
            )
            balances = balance_data.get('balances', {})
            self.log_with_clock(logging.INFO, f"Balances: {balances}")
        except Exception as e:
            self.log_with_clock(logging.ERROR, f"Error fetching balances: {str(e)}")

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if self._executed:
            return "✅ Trade has been executed successfully!"

        lines = []

        lines.append("=== Minswap AMM Liquidity Action ===")
        lines.append(f"Gateway: {self.config.connector}")
        lines.append(f"Chain/Network: {self.config.chain}/{self.config.network}")
        lines.append(f"Pair: {self.config.trading_pair}")

        if self._task_running:
            lines.append("\nStatus: 🔄 Trade in progress...")
            if self.trade_start_time:
                elapsed = (datetime.now() - self.trade_start_time).total_seconds()
                lines.append(f"Time elapsed: {int(elapsed)}s")
        else:
            lines.append("\nStatus: ⏳ Ready to execute trade...")

        return "\n".join(lines)
