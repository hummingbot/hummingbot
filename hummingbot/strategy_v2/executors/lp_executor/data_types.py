from decimal import Decimal
from enum import Enum
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.models.executors import TrackedOrder


class LPExecutorStates(Enum):
    """
    State machine for LP position lifecycle.
    Price direction (above/below range) is determined from custom_info, not state.
    """
    NOT_ACTIVE = "NOT_ACTIVE"              # No position, no pending orders
    OPENING = "OPENING"                    # add_liquidity submitted, waiting
    IN_RANGE = "IN_RANGE"                  # Position active, price within bounds
    OUT_OF_RANGE = "OUT_OF_RANGE"          # Position active, price outside bounds
    CLOSING = "CLOSING"                    # remove_liquidity submitted, waiting
    SWAPPING = "SWAPPING"                  # Close-out swap in progress (keep_position=False)
    COMPLETE = "COMPLETE"                  # Position closed permanently
    FAILED = "FAILED"                      # Max retries reached, manual intervention required


class LPExecutorConfig(ExecutorConfigBase):
    """
    Configuration for LP Position Executor.

    - Creates position based on config bounds and amounts
    - Monitors position state (IN_RANGE, OUT_OF_RANGE)
    - Closes when price exceeds upper_limit_price or lower_limit_price
    - Closes position when executor stops (unless keep_position=True)

    Provider Architecture:
    - connector_name: The network identifier (e.g., "solana-mainnet-beta")
      This is the "connector" that hummingbot connects to.
    - lp_provider: LP provider in format "dex/trading_type" (e.g., "meteora/clmm")
      Used for pool info, add liquidity, remove liquidity operations.
    - swap_provider: Optional swap provider for close-out swaps when keep_position=False.
      If not provided, uses the network's default swap provider.
    """
    type: Literal["lp_executor"] = "lp_executor"

    # Network connector - e.g., "solana-mainnet-beta"
    connector_name: str

    # LP provider (required) - format: "dex/trading_type"
    # Examples: "meteora/clmm", "orca/clmm", "raydium/clmm"
    # Used for pool operations: get_pool_info, add_liquidity, remove_liquidity
    lp_provider: str

    # Swap provider (optional) - format: "dex/trading_type"
    # Examples: "jupiter/router", "orca/router"
    # Used for close-out swaps when keep_position=False to return to original quote asset.
    # If None, uses the network's default swap provider.
    swap_provider: Optional[str] = None

    # Pool identification (required)
    pool_address: str

    # Trading pair for the pool (required) - e.g., "SOL-USDC"
    trading_pair: str

    # Position price bounds
    lower_price: Decimal
    upper_price: Decimal

    # Position amounts
    base_amount: Decimal = Decimal("0")
    quote_amount: Decimal = Decimal("0")

    # Position side: TradeType.BUY (quote only), TradeType.SELL (base only), TradeType.RANGE (50/50)
    side: TradeType

    # Limit prices: close position when price exceeds these limits
    # Works like grid executor - closes when price goes beyond the limit
    # upper_limit_price: close when price >= this value (None = no upper limit)
    # lower_limit_price: close when price <= this value (None = no lower limit)
    upper_limit_price: Optional[Decimal] = None
    lower_limit_price: Optional[Decimal] = None

    # Connector-specific params
    extra_params: Optional[Dict] = None  # e.g., {"strategyType": 0} for Meteora

    # Position tracking behavior
    keep_position: bool = True  # If True, store net token change as spot position when closed

    model_config = ConfigDict(arbitrary_types_allowed=True)


class LPExecutorState(BaseModel):
    """Tracks a single LP position state within executor."""
    position_address: Optional[str] = None
    lower_price: Decimal = Decimal("0")
    upper_price: Decimal = Decimal("0")
    base_amount: Decimal = Decimal("0")
    quote_amount: Decimal = Decimal("0")
    base_fee: Decimal = Decimal("0")
    quote_fee: Decimal = Decimal("0")

    # Actual amounts deposited at ADD time (for accurate P&L calculation)
    # Note: base_amount/quote_amount above change as price moves; these are fixed
    initial_base_amount: Decimal = Decimal("0")
    initial_quote_amount: Decimal = Decimal("0")

    # Market price at ADD time for accurate P&L calculation
    add_mid_price: Decimal = Decimal("0")

    # Rent and fee tracking
    position_rent: Decimal = Decimal("0")  # SOL rent paid to create position (ADD only)
    position_rent_refunded: Decimal = Decimal("0")  # SOL rent refunded on close (REMOVE only)
    tx_fee: Decimal = Decimal("0")  # Transaction fee paid (both ADD and REMOVE)

    # Transaction hashes for tracking
    open_tx_hash: Optional[str] = None  # Transaction hash for ADD
    close_tx_hash: Optional[str] = None  # Transaction hash for REMOVE

    # Order tracking
    active_open_order: Optional[TrackedOrder] = None
    active_close_order: Optional[TrackedOrder] = None
    active_swap_order: Optional[TrackedOrder] = None  # Close-out swap order

    # State
    state: LPExecutorStates = LPExecutorStates.NOT_ACTIVE

    # Timestamp when position went out of range (for calculating duration)
    _out_of_range_since: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_out_of_range_seconds(self, current_time: float) -> Optional[int]:
        """Returns seconds the position has been out of range, or None if in range."""
        if self._out_of_range_since is None:
            return None
        return int(current_time - self._out_of_range_since)

    def update_state(self, current_price: Optional[Decimal] = None, current_time: Optional[float] = None):
        """
        Update state based on position_address and price.
        Called each control_task cycle.

        Note: We don't use TrackedOrder.is_filled since it's read-only.
        Instead, we check:
        - position_address set = position was created
        - state == COMPLETE (set by event handler) = position was closed

        Args:
            current_price: Current market price
            current_time: Current timestamp (for tracking _out_of_range_since)
        """
        # If already complete, closing, swapping, failed, or opening (waiting for retry), preserve state
        # These states are managed explicitly by the executor, don't overwrite them
        if self.state in (LPExecutorStates.COMPLETE, LPExecutorStates.CLOSING, LPExecutorStates.SWAPPING, LPExecutorStates.FAILED):
            return

        # Preserve OPENING state when no position exists (handles max_retries case)
        # State only transitions from OPENING when position_address is set
        if self.state == LPExecutorStates.OPENING and self.position_address is None:
            return

        # If closing order is active, we're closing
        if self.active_close_order is not None:
            self.state = LPExecutorStates.CLOSING
            return

        # If open order is active but position not yet created, we're opening
        if self.active_open_order is not None and self.position_address is None:
            self.state = LPExecutorStates.OPENING
            return

        # Position exists - determine state based on price location
        if self.position_address and current_price is not None:
            if current_price < self.lower_price or current_price > self.upper_price:
                self.state = LPExecutorStates.OUT_OF_RANGE
            else:
                self.state = LPExecutorStates.IN_RANGE
        elif self.position_address is None:
            self.state = LPExecutorStates.NOT_ACTIVE

        # Track _out_of_range_since timer (matches original script logic)
        if self.state == LPExecutorStates.IN_RANGE:
            # Price back in range - reset timer
            self._out_of_range_since = None
        elif self.state == LPExecutorStates.OUT_OF_RANGE:
            # Price out of bounds - start timer if not already started
            if self._out_of_range_since is None and current_time is not None:
                self._out_of_range_since = current_time
