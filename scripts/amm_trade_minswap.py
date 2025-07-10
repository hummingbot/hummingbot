import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AmmTradeConfig(BaseClientModel):
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
        "BUY",
        json_schema_extra={"prompt": "Trade side (BUY or SELL)", "prompt_on_new": True}
    )
    order_amount: Decimal = Field(
        Decimal("10"),
        json_schema_extra={"prompt": "Order amount for the trade", "prompt_on_new": True}
    )
    slippage_buffer: Decimal = Field(
        Decimal("0.01"),
        json_schema_extra={"prompt": "Slippage buffer (e.g. 0.01 for 1%)", "prompt_on_new": False}
    )


class AmmTradeMinswap(ScriptStrategyBase):
    """
    This strategy executes a single AMM trade on Minswap with slippage protection.
    """

    @classmethod
    def init_markets(cls, config: AmmTradeConfig):
        # No on-chain markets → skip readiness polling
        cls.markets = {}

    def __init__(self, connectors: Dict[str, object], config: AmmTradeConfig):
        super().__init__(connectors)
        self.config = config
        self.base, self.quote = config.trading_pair.split("-")
        # Map to the enum the HTTP client expects:
        self.trade_type = TradeType.BUY if config.side.upper() == "BUY" else TradeType.SELL

        # State tracking
        self.on_going_task = False
        self.trade_executed = False
        self.trade_start_time = None

        # Log trade information
        side = self.config.side.upper()
        self.log_with_clock(logging.INFO, f"Will {side} {self.config.order_amount} {self.quote} for {self.base} on {self.config.connector}/{self.config.chain}_{self.config.network}")
        self.log_with_clock(logging.INFO, f"Slippage buffer: {self.config.slippage_buffer * 100}%")

    def on_tick(self):
        if not self.on_going_task and not self.trade_executed:
            self.on_going_task = True
            self.trade_start_time = datetime.now()
            safe_ensure_future(self.async_task())

    async def async_task(self):
        try:
            # Get wallet address from gateway connections
            gateway_connections_conf = GatewayConnectionSetting.load()
            wallet = next(
                (w for w in gateway_connections_conf
                 if w["chain"] == self.config.chain
                 and w["connector"] == self.config.connector
                 and w["network"] == self.config.network), None
            )
            if not wallet:
                self.log_with_clock(logging.ERROR, "No wallet configured for the specified chain, connector, and network.")
                return

            address = wallet["wallet_address"]

            # Get initial balances
            await self.get_balance(address, [self.base, self.quote])

            # Fetch current price
            self.log_with_clock(logging.INFO, f"Fetching price for {self.config.trading_pair}...")
            price_data = await GatewayHttpClient.get_instance().get_price(
                self.config.chain,
                self.config.network,
                self.config.connector,
                self.base,
                self.quote,
                self.config.order_amount,
                self.trade_type
            )

            price = float(price_data.get("price", 0))
            self.log_with_clock(logging.INFO, f"Current Price: {price}")

            # Log additional price details
            estimated_amount_in = price_data.get("estimatedAmountIn", "N/A")
            estimated_amount_out = price_data.get("estimatedAmountOut", "N/A")
            min_amount_out = price_data.get("minAmountOut", "N/A")

            self.log_with_clock(logging.INFO, f"Estimated Amount In: {estimated_amount_in}")
            self.log_with_clock(logging.INFO, f"Estimated Amount Out: {estimated_amount_out}")
            self.log_with_clock(logging.INFO, f"Min Amount Out (with slippage): {min_amount_out}")

            # Apply slippage buffer
            slippage_multiplier = 1 + float(self.config.slippage_buffer) if self.trade_type == TradeType.BUY else 1 - float(self.config.slippage_buffer)
            adjusted_price = price * slippage_multiplier
            self.log_with_clock(logging.INFO, f"Adjusted Price with Slippage: {adjusted_price}")

            # Execute trade
            self.log_with_clock(logging.INFO, "Executing trade...")
            order_amount = int(self.config.order_amount)
            trade_data = await GatewayHttpClient.get_instance().execute_swap(
                self.config.network,
                self.config.connector,
                address,
                self.base,
                self.quote,
                self.trade_type,
                order_amount,
            )
            tx_hash = trade_data.get("signature")
            if tx_hash:
                self.log_with_clock(logging.INFO, f"Trade submitted with transaction hash: {tx_hash}")

                # Poll transaction status
                await self.poll_transaction(tx_hash)

                # Get final balances
                await self.get_balance(address, [self.base, self.quote])

                # Mark trade as executed
                self.trade_executed = True
                self.log_with_clock(logging.INFO, "Trade executed successfully. No further trades will be made.")
            else:
                self.log_with_clock(logging.ERROR, "Failed to get transaction hash from trade response")

        except Exception as e:
            self.log_with_clock(logging.ERROR, f"Error in async_task: {str(e)}")
        finally:
            self.on_going_task = False

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

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if self.trade_executed:
            return "✅ Trade has been executed successfully!"

        lines = []
        side = self.config.side.upper()

        lines.append("=== Minswap AMM Trade ===")
        lines.append(f"Gateway: {self.config.connector}")
        lines.append(f"Chain/Network: {self.config.chain}/{self.config.network}")
        lines.append(f"Pair: {self.base}-{self.quote}")
        lines.append(f"Strategy: {side} {self.config.order_amount} {self.base} for {self.quote}")
        lines.append(f"Slippage: {self.config.slippage_buffer * 100}%")

        if self.on_going_task:
            lines.append("\nStatus: 🔄 Trade in progress...")
            if self.trade_start_time:
                elapsed = (datetime.now() - self.trade_start_time).total_seconds()
                lines.append(f"Time elapsed: {int(elapsed)}s")
        else:
            lines.append("\nStatus: ⏳ Ready to execute trade...")

        return "\n".join(lines)
