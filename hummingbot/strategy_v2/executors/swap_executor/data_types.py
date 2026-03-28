"""
Data types for SwapExecutor.

Defines configuration and state enums for single swap execution on Gateway AMM connectors.
"""
from decimal import Decimal
from enum import Enum
from typing import List, Literal, Optional

from pydantic import ConfigDict

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase


class SwapExecutorStates(Enum):
    """State machine for swap execution lifecycle."""
    NOT_STARTED = "NOT_STARTED"  # Initial state, swap not yet attempted
    EXECUTING = "EXECUTING"      # Swap submitted, waiting for confirmation
    COMPLETED = "COMPLETED"      # Swap successfully completed
    FAILED = "FAILED"            # Swap failed after max retries


class SwapExecutorConfig(ExecutorConfigBase):
    """
    Configuration for Swap Executor.

    Executes a single swap on a Gateway AMM connector with retry logic
    for handling transaction timeouts and failures.
    """
    type: Literal["swap_executor"] = "swap_executor"

    # Network identification (e.g., "solana-mainnet-beta", "ethereum-mainnet")
    network: str
    trading_pair: str

    # Trade parameters
    side: TradeType        # BUY or SELL
    amount: Decimal        # Base token amount to swap

    # Optional parameters
    slippage_pct: Optional[Decimal] = None  # Override connector default slippage

    # Multi-provider quote comparison
    # If set, fetches quotes from all providers and executes with best price
    # Example: ["jupiter/router", "meteora/clmm", "orca/clmm"]
    # If not set, uses default swap provider for the chain (e.g., jupiter/router for solana)
    swap_providers: Optional[List[str]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
