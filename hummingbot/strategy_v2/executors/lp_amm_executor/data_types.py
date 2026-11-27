from decimal import Decimal
from enum import Enum
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.validation import (
    require_non_empty,
    require_non_negative,
    require_not_above,
    require_positive,
    require_provider,
    require_trading_pair,
)
from hummingbot.strategy_v2.models.executors import TrackedOrder


class LPAmmExecutorStates(Enum):
    """
    State machine for a full-range constant-product AMM position lifecycle.

    There is no IN_RANGE/OUT_OF_RANGE here: a full-range AMM position provides
    liquidity across the whole price curve by construction, so ACTIVE covers
    the entire time the position is open. Exiting is decided by min_fee_apr_pct
    and max_duration_seconds instead of a price range.
    """
    NOT_ACTIVE = "NOT_ACTIVE"      # No position, no pending orders
    OPENING = "OPENING"            # add_liquidity submitted, waiting
    ACTIVE = "ACTIVE"              # Position open, earning/losing against the no-fee curve
    CLOSING = "CLOSING"            # remove_liquidity submitted, waiting
    SWAPPING = "SWAPPING"          # Close-out swap in progress (keep_position=False)
    COMPLETE = "COMPLETE"          # Position closed permanently
    FAILED = "FAILED"              # Max retries reached, manual intervention required


class LPAmmExecutorConfig(ExecutorConfigBase):
    """
    Configuration for the full-range AMM LP executor.

    Unlike LPExecutorConfig (CLMM), there are no lower_price/upper_price fields:
    a constant-product AMM position is full-range by construction. In place of
    closing when price leaves a range, this executor closes when the realized
    fee APR falls below min_fee_apr_pct, or when max_duration_seconds elapses —
    whichever comes first.

    Provider Architecture (mirrors LPExecutorConfig):
    - connector_name: the network identifier (e.g. "solana-mainnet-beta")
    - lp_provider: "dex/amm" (e.g. "meteora/amm"), used for pool info and the
      add/remove-liquidity routes.
    """
    type: Literal["lp_amm_executor"] = "lp_amm_executor"

    connector_name: str
    lp_provider: str

    # Swap provider (optional) - format: "dex/trading_type", e.g. "jupiter/router".
    # Used for the close-out swap when keep_position=False, to swap any leftover
    # single-sided token balance back to the initial deposit's base/quote target
    # after withdrawal. If None, uses the network's default swap provider.
    swap_provider: Optional[str] = None

    pool_address: str
    trading_pair: str

    # Always RANGE: a constant-product AMM deposit is two-sided by construction,
    # never a single-sided BUY/SELL. Required so the orchestrator's PositionHold
    # ledger (executor_orchestrator.py's add_orders_from_executor/_determine_position_side,
    # which unconditionally reads executor_info.config.side even in a plain log line)
    # does not raise AttributeError the first time this executor ends in POSITION_HOLD.
    side: TradeType = TradeType.RANGE

    base_amount: Decimal = Decimal("0")
    quote_amount: Decimal = Decimal("0")

    # Minimum time between on-chain position reads, same rationale as LPExecutor's:
    # keep the control loop responsive without making one Gateway request per tick.
    position_refresh_interval: float = 1.0

    # Exit triggers, in place of the CLMM range checks.
    # min_fee_apr_pct is ignored until the position has been open for at least
    # min_fee_apr_window_seconds: an APR annualized from a few seconds of fees
    # is noise, not a measurement.
    min_fee_apr_pct: Optional[Decimal] = None
    min_fee_apr_window_seconds: float = 3600.0
    max_duration_seconds: Optional[float] = None

    # Slippage ramp, identical contract to LPExecutorConfig's: starts tight,
    # widens only on a failure Gateway attributed to slippage, never past
    # max_slippage_pct.
    slippage_pct: Decimal = Decimal("0.05")
    slippage_multiplier: Decimal = Decimal("5")
    max_slippage_pct: Decimal = Decimal("5")

    # Connector-specific params (e.g. strategy-specific knobs some DEXes take)
    extra_params: Optional[Dict] = None

    # What to do when the executor closes *itself* (an exit trigger fires). A
    # caller-initiated stop passes its own keep_position to early_stop(), which
    # overrides this. True: keep the round trip's net token change and record
    # it as a spot position. False: report it as a plain early stop.
    keep_position: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def validate_lp_amm_position(self):
        require_non_empty("connector_name", self.connector_name)
        require_provider("lp_provider", self.lp_provider)
        # swap_provider carries a trading type too, so a bare name is rejected here
        # instead of surfacing as a 400 mid close-out swap, with the position's
        # funds exposed.
        require_provider("swap_provider", self.swap_provider, required=False)
        require_non_empty("pool_address", self.pool_address)
        require_trading_pair("trading_pair", self.trading_pair)
        require_non_negative("base_amount", self.base_amount)
        require_non_negative("quote_amount", self.quote_amount)
        if self.base_amount == 0 and self.quote_amount == 0:
            raise ValueError(
                "base_amount and quote_amount cannot both be 0: "
                "at least one side of the position has to be funded"
            )
        require_positive("position_refresh_interval", self.position_refresh_interval)
        require_positive("min_fee_apr_pct", self.min_fee_apr_pct)
        require_positive("min_fee_apr_window_seconds", self.min_fee_apr_window_seconds)
        require_positive("max_duration_seconds", self.max_duration_seconds)
        require_positive("slippage_pct", self.slippage_pct)
        require_positive("max_slippage_pct", self.max_slippage_pct)
        require_not_above("slippage_pct", self.slippage_pct, "max_slippage_pct", self.max_slippage_pct)
        if self.slippage_multiplier <= 1:
            raise ValueError(f"slippage_multiplier must be greater than 1, got {self.slippage_multiplier}")
        return self


class LPAmmExecutorState(BaseModel):
    """Tracks a single full-range AMM LP position within the executor."""

    # True once add_liquidity has landed and amounts are booked. Unlike
    # LPExecutorState's position_address check, this can't be "position
    # identity is set" because a fungible-LP position (see position_nft_address
    # below) never gets one.
    position_opened: bool = False

    # None identifies a fungible-LP holding, where the pool address alone names
    # the wallet's share. Set, it is the NFT position address for an
    # NFT-backed AMM (e.g. Meteora DAMM v2), where a wallet may hold several
    # positions in the same pool.
    position_nft_address: Optional[str] = None

    base_amount: Decimal = Decimal("0")
    quote_amount: Decimal = Decimal("0")

    # For a fungible-LP pool only (position_nft_address is None): this deposit's own
    # share of the wallet's pool-wide LP-token balance, captured as the delta across
    # the add_liquidity call. None when it could not be captured (the pre-deposit
    # snapshot read failed) - closing then falls back to removing the wallet's whole
    # balance, which is unsafe if the wallet holds other liquidity in the same pool.
    own_lp_token_amount: Optional[Decimal] = None

    # Amounts and price at ADD time, fixed for the life of the position -
    # used to compute fees earned / impermanent loss / fee APR against.
    initial_base_amount: Decimal = Decimal("0")
    initial_quote_amount: Decimal = Decimal("0")
    add_price: Decimal = Decimal("0")
    add_timestamp: Optional[float] = None

    tx_fee: Decimal = Decimal("0")

    # Fees earned as of the close confirmation, frozen before any close-out swap can
    # mutate base_amount/quote_amount - see fees_earned_quote below.
    realized_fees_earned_quote: Optional[Decimal] = None

    open_tx_hash: Optional[str] = None
    close_tx_hash: Optional[str] = None

    # Gateway's AMM remove-liquidity response carries neither the removed
    # amounts nor a close tx fee back to the executor (unlike the CLMM close),
    # so this stays False always for now - see LPAmmExecutor._close_position.
    open_data_unavailable: bool = False
    close_data_unavailable: bool = False

    active_open_order: Optional[TrackedOrder] = None
    active_close_order: Optional[TrackedOrder] = None
    active_swap_order: Optional[TrackedOrder] = None  # Close-out swap order

    state: LPAmmExecutorStates = LPAmmExecutorStates.NOT_ACTIVE

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def invariant_k(self) -> Decimal:
        """The constant-product invariant this deposit's own share traces out.

        A balanced deposit into a constant-product pool divides value evenly
        between base and quote at the price it was made, so
        initial_base_amount * initial_quote_amount is the k of the "mini pool"
        the deposit's share follows as price moves - which is what
        value_no_fee_quote below is derived from.
        """
        return self.initial_base_amount * self.initial_quote_amount

    def value_no_fee_quote(self, current_price: Decimal) -> Decimal:
        """What this deposit's share would be worth now had it earned zero fees.

        The standard constant-product "no fee" value curve: 2 * sqrt(k * price).
        current_value_quote cannot fall below this from price movement alone;
        anything above it came from fees.
        """
        k = self.invariant_k()
        if k <= 0 or current_price <= 0:
            return Decimal("0")
        return 2 * (k * current_price).sqrt()

    def current_value_quote(self, current_price: Decimal) -> Decimal:
        """The position's current redeemable value, in quote."""
        return self.base_amount * current_price + self.quote_amount

    def held_value_quote(self, current_price: Decimal) -> Decimal:
        """What simply holding the initial deposit (never LPing) would be worth now."""
        return self.initial_base_amount * current_price + self.initial_quote_amount

    def fees_earned_quote(self, current_price: Decimal) -> Decimal:
        """Value growth attributable to fees rather than price movement.

        current_value already includes fee growth for a full-range AMM - fees
        accrue into the pool's reserves, not a separate ledger - so this is
        current value minus the no-fee curve, floored at 0 against measurement
        noise right after the position opens.

        Once realized_fees_earned_quote is set (close confirmed), that frozen
        figure is returned instead: base_amount/quote_amount keep being read
        for total_value_quote after a close-out swap trades them, and running
        this formula against the swapped amounts would book the swap's own
        price difference from current_price as LP fees (and, through
        filled_amount_quote, as pool volume that never happened).
        """
        if self.realized_fees_earned_quote is not None:
            return self.realized_fees_earned_quote
        fees = self.current_value_quote(current_price) - self.value_no_fee_quote(current_price)
        return fees if fees > 0 else Decimal("0")

    def impermanent_loss_quote(self, current_price: Decimal) -> Decimal:
        """Value given up to price divergence alone, net of fees.

        Always >= 0 by AM-GM: holding beats an un-fee'd constant-product
        position whenever price has moved from the deposit price, in either
        direction.
        """
        il = self.held_value_quote(current_price) - self.value_no_fee_quote(current_price)
        return il if il > 0 else Decimal("0")

    def fee_apr_pct(self, current_price: Decimal, current_time: float) -> Optional[Decimal]:
        """Annualized realized fee rate on the initial deposit, or None.

        None before add_timestamp is known or at zero elapsed time - an APR
        extrapolated from an instant is not a measurement.
        """
        if self.add_timestamp is None or self.add_price <= 0:
            return None
        elapsed = Decimal(str(current_time)) - Decimal(str(self.add_timestamp))
        if elapsed <= 0:
            return None
        initial_value = self.held_value_quote(self.add_price)
        if initial_value <= 0:
            return None
        fees = self.fees_earned_quote(current_price)
        seconds_per_year = Decimal("31536000")
        return (fees / initial_value) * (seconds_per_year / elapsed) * Decimal("100")

    def update_state(self):
        """
        Promote state once the open/close orders resolve. Called each
        control_task cycle.

        Unlike LPExecutorState.update_state, ACTIVE does not depend on price:
        a full-range position provides liquidity at every price, so there is
        no range check here.
        """
        if self.state in (
            LPAmmExecutorStates.COMPLETE, LPAmmExecutorStates.CLOSING,
            LPAmmExecutorStates.SWAPPING, LPAmmExecutorStates.FAILED,
        ):
            return

        if self.state == LPAmmExecutorStates.OPENING and not self.position_opened:
            return

        if self.active_close_order is not None:
            self.state = LPAmmExecutorStates.CLOSING
            return

        if self.active_open_order is not None and not self.position_opened:
            self.state = LPAmmExecutorStates.OPENING
            return

        self.state = LPAmmExecutorStates.ACTIVE if self.position_opened else LPAmmExecutorStates.NOT_ACTIVE
