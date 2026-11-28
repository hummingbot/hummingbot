import logging
from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.gateway_utils import parse_provider
from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class LPAmmRebalancerConfig(ControllerConfigBase):
    """
    Configuration for the full-range AMM LP controller.

    Unlike LPRebalancerConfig (CLMM), there is no price-range/side logic here: a
    constant-product AMM position is full-range and two-sided by construction, and
    LPAmmExecutor already decides when to close itself (min_fee_apr_pct /
    max_duration_seconds). This controller's job is just to keep one position open,
    hand its config to a fresh LPAmmExecutor, and - if reopen_after_close is set -
    open the next one once the previous one terminates cleanly.
    """
    controller_type: str = "generic"
    controller_name: str = "lp_amm_rebalancer"
    candles_config: List[CandlesConfig] = []

    # Network connector - e.g., "solana-mainnet-beta"
    connector_name: str = "solana-mainnet-beta"

    # LP provider (required) - format: "dex/amm", e.g. "meteora/amm"
    lp_provider: str = "meteora/amm"

    # Swap provider (optional) - format: "dex/trading_type", used for the close-out
    # swap when keep_position=False. None uses the network's default swap provider.
    swap_provider: Optional[str] = None

    # Pool configuration (required)
    trading_pair: str
    pool_address: str

    # Position amounts, deposited as-is every time a position is (re)opened
    base_amount: Decimal = Field(default=Decimal("0"), json_schema_extra={"is_updatable": True})
    quote_amount: Decimal = Field(default=Decimal("0"), json_schema_extra={"is_updatable": True})

    # Exit triggers, forwarded to LPAmmExecutorConfig as-is
    min_fee_apr_pct: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    min_fee_apr_window_seconds: float = Field(default=3600.0, json_schema_extra={"is_updatable": True})
    max_duration_seconds: Optional[float] = Field(default=None, json_schema_extra={"is_updatable": True})

    # True: on a self-triggered exit, keep the net token change as a held position
    # instead of swapping back. Forwarded to LPAmmExecutorConfig as-is.
    keep_position: bool = Field(default=False, json_schema_extra={"is_updatable": True})

    slippage_pct: Decimal = Field(default=Decimal("0.05"), json_schema_extra={"is_updatable": True})

    position_refresh_interval: float = Field(
        default=1.0,
        gt=0,
        json_schema_extra={"is_updatable": False},
        description="Minimum seconds between on-chain position reads made by the LP executor. "
                    "Captured when the executor is created; not live-updatable."
    )

    # Once the active executor terminates cleanly, open a new position with the same
    # base_amount/quote_amount. False: stop after the first position closes.
    reopen_after_close: bool = Field(default=True, json_schema_extra={"is_updatable": True})

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """Register the LP connector with trading pair"""
        markets = markets.add_or_update(self.connector_name, self.trading_pair)
        return markets


class LPAmmRebalancer(ControllerBase):
    """
    Controller for full-range AMM LP position management.

    Keeps at most one LPAmmExecutor active at a time. The executor itself owns the
    exit decision (fee APR / max duration); this controller only reacts to it
    terminating: clean terminations (COMPLETE/EARLY_STOP/POSITION_HOLD with the
    position actually closed) feed position_hold bookkeeping and - if configured -
    open the next position, while an unresolved on-chain position (hold_reason
    close_retries_exhausted) halts new creation until it is recovered manually.
    """

    _logger: Optional[HummingbotLogger] = None

    # A bare pre-flight failure (e.g. Gateway's INSUFFICIENT_BALANCE) terminates almost
    # instantly with nothing on-chain, so without a cap determine_executor_actions would
    # recreate the executor every tick forever, hammering Gateway/RPC. Halt instead once
    # the same failure repeats this many times in a row.
    MAX_CONSECUTIVE_PREFLIGHT_FAILURES: int = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, config: LPAmmRebalancerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config: LPAmmRebalancerConfig = config

        self._current_executor_id: Optional[str] = None
        # Set when a terminated executor still has a live on-chain position (close
        # retries exhausted): halts new position creation until it is recovered
        # manually, same contract as LPRebalancer's _orphaned_position_address.
        self._orphaned_position_address: Optional[str] = None

        # Position hold: cumulative net position from closed LP executors.
        # Net = (returned + fee) - initial_deposited, same bookkeeping as LPRebalancer's.
        self._position_hold_base: Decimal = Decimal("0")
        self._position_hold_quote: Decimal = Decimal("0")

        self._stopped_after_close: bool = False

        # Consecutive bare pre-flight failures (nothing ever reached the chain), and
        # whether that streak has crossed MAX_CONSECUTIVE_PREFLIGHT_FAILURES and halted
        # new creation. Reset to 0 the moment any executor gets past pre-flight.
        self._consecutive_preflight_failures: int = 0
        self._halted_preflight_failures: bool = False

        # Runs once, before this controller instance's first executor creation, to
        # detect a position left open in the pool by a previous session (e.g. a
        # restart while a position was active) - without it, determine_executor_actions
        # has no record of that position and opens a fresh one on top of it.
        self._startup_position_check_done: bool = False

    def active_executor(self) -> Optional[ExecutorInfo]:
        """Get the current active LP AMM executor (should be 0 or 1)."""
        active = [e for e in self.executors_info
                  if e.is_active and getattr(e.config, "type", None) == "lp_amm_executor"]
        return active[0] if active else None

    def get_tracked_executor(self) -> Optional[ExecutorInfo]:
        """Get the executor we're currently tracking (by ID)."""
        if not self._current_executor_id:
            return None
        for e in self.executors_info:
            if e.id == self._current_executor_id:
                return e
        return None

    def is_tracked_executor_terminated(self) -> bool:
        """Check if the executor we created has terminated."""
        if not self._current_executor_id:
            return True
        executor = self.get_tracked_executor()
        if executor is None:
            return True
        return executor.status == RunnableStatus.TERMINATED

    def determine_executor_actions(self) -> List[ExecutorAction]:
        actions: List[ExecutorAction] = []

        # The startup check (update_processed_data) must have actually succeeded once
        # before any position is created - a pool read that keeps failing is not proof
        # the pool is empty, and creating on top of an unseen existing position would
        # double the real on-chain exposure.
        if not self._startup_position_check_done:
            self.logger().debug(
                f"Halted: waiting for the startup check of pool {self.config.pool_address} "
                "for an existing position to succeed."
            )
            return actions

        # An orphaned on-chain position (close retries exhausted) must be recovered
        # before any new position is opened - creating a fresh executor here would
        # stack live exposure on top of the stranded one.
        if self._orphaned_position_address:
            self.logger().debug(
                f"Halted: position {self._orphaned_position_address} is still open on-chain "
                "and requires manual recovery."
            )
            return actions

        if self._halted_preflight_failures:
            self.logger().debug(
                f"Halted: {self._consecutive_preflight_failures} consecutive position-creation "
                "failures with nothing reaching the chain - fix the underlying issue (e.g. wallet "
                "balance) and restart the controller."
            )
            return actions

        if self._stopped_after_close:
            return actions

        executor = self.active_executor()

        if executor and not self._current_executor_id:
            self._current_executor_id = executor.id
            self.logger().info(f"Tracking executor: {executor.id}")

        if executor is not None:
            # Active executor exists - nothing to do, it closes itself.
            return actions

        if not self.is_tracked_executor_terminated():
            tracked = self.get_tracked_executor()
            self.logger().debug(
                f"Waiting for executor {self._current_executor_id} to terminate "
                f"(status: {tracked.status if tracked else 'not found'})"
            )
            return actions

        # Either no executor has ever run, or the tracked one just terminated.
        terminated_executor = self.get_tracked_executor()
        self._current_executor_id = None

        if terminated_executor is not None:
            self._process_terminated_executor(terminated_executor)
            if self._orphaned_position_address or self._halted_preflight_failures:
                return actions
            if not self.config.reopen_after_close:
                self._stopped_after_close = True
                self.logger().info("Position closed and reopen_after_close is False - not reopening.")
                return actions

        executor_config = self._create_executor_config()
        actions.append(CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=executor_config,
        ))
        return actions

    def _process_terminated_executor(self, terminated_executor: ExecutorInfo) -> None:
        """Book the terminated executor's net position change, and detect an orphan."""
        custom = terminated_executor.custom_info
        hold_reason = custom.get("hold_reason")

        # FAILED with no open transaction in flight is a genuine pre-flight rejection -
        # nothing was ever deposited, nothing to book, safe to reopen. But a config that
        # can never succeed (e.g. the wallet can't cover base_amount/quote_amount) would
        # otherwise fail and reopen forever - halt once the same failure repeats too often.
        if terminated_executor.close_type == CloseType.FAILED and custom.get("open_tx_hash") is None:
            self._consecutive_preflight_failures += 1
            if self._consecutive_preflight_failures >= self.MAX_CONSECUTIVE_PREFLIGHT_FAILURES:
                self._halted_preflight_failures = True
                self.logger().error(
                    f"Executor {terminated_executor.id} ended FAILED with nothing on-chain "
                    f"{self._consecutive_preflight_failures} times in a row - halting new position "
                    "creation until the controller is restarted or reconfigured."
                )
            else:
                self.logger().warning(
                    f"Executor {terminated_executor.id} ended FAILED with nothing on-chain "
                    f"({self._consecutive_preflight_failures}/{self.MAX_CONSECUTIVE_PREFLIGHT_FAILURES}) - "
                    "skipping position_hold update."
                )
            return
        self._consecutive_preflight_failures = 0

        # closeout_swap_failed means the LP withdrawal already landed on-chain and the
        # close-out swap definitively did not (rejected, cancelled, or no swap_provider) -
        # there is no open or pending position to protect, so book the withdrawal like a
        # normal completion and stay eligible to reopen. This deliberately excludes
        # closeout_swap_unresolved: that swap's outcome is unknown and it may still land,
        # competing with a new deposit for the same funds, so it falls through to the halt
        # branch below like any other live-exposure hold.
        if hold_reason == "closeout_swap_failed":
            self.logger().warning(
                f"Executor {terminated_executor.id} closed its LP position but the close-out "
                "swap failed - booking the withdrawal and remaining eligible to reopen."
            )
            self._book_net_position(terminated_executor, custom)
            return

        # Any other involuntary hold means the deposit landed, or may still land, and the
        # executor could not manage it any further. A FAILED terminal that still carries an
        # open_tx_hash is the same exposure under a different close_type: the add
        # transaction's outcome was unresolved. Either way, halt new creation rather than
        # stacking a second position on top of possibly-live exposure.
        if hold_reason or terminated_executor.close_type == CloseType.FAILED:
            self._orphaned_position_address = (
                custom.get("position_nft_address") or self.config.pool_address
            )
            self.logger().error(
                f"Executor {terminated_executor.id} ended {terminated_executor.close_type} "
                f"with a position still open (or unresolved) on-chain in pool "
                f"{self.config.pool_address}. Halting new position creation until the "
                "position is closed or recovered manually."
            )
            return

        self._book_net_position(terminated_executor, custom)

    def _book_net_position(self, terminated_executor: ExecutorInfo, custom: dict) -> None:
        base_amount = Decimal(str(custom.get("base_amount", 0)))
        quote_amount = Decimal(str(custom.get("quote_amount", 0)))
        # tx_fee is paid in the network's native token (SOL, etc.), not quote - subtracting
        # it straight from quote tokens would misprice the cost for any pair where the two
        # differ. tx_fee_quote is the same fee already converted at the executor's own rate.
        tx_fee_quote = Decimal(str(custom.get("tx_fee_quote", 0)))
        initial_base = Decimal(str(custom.get("initial_base_amount", 0)))
        initial_quote = Decimal(str(custom.get("initial_quote_amount", 0)))

        base_net = base_amount - initial_base
        quote_net = (quote_amount - tx_fee_quote) - initial_quote
        self._position_hold_base += base_net
        self._position_hold_quote += quote_net

        self.logger().info(
            f"Executor {terminated_executor.id} completed ({terminated_executor.close_type}). "
            f"Initial: base={initial_base}, quote={initial_quote}. Returned: base={base_amount}, "
            f"quote={quote_amount} (tx_fee_quote={tx_fee_quote}). Net change: base={base_net:+}, quote={quote_net:+}. "
            f"Position hold total: base={self._position_hold_base}, quote={self._position_hold_quote}"
        )

    def _create_executor_config(self) -> LPAmmExecutorConfig:
        self.logger().info(
            f"Creating LPAmmExecutor: pool={self.config.pool_address}, "
            f"base={self.config.base_amount}, quote={self.config.quote_amount}"
        )
        return LPAmmExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            lp_provider=self.config.lp_provider,
            swap_provider=self.config.swap_provider,
            trading_pair=self.config.trading_pair,
            pool_address=self.config.pool_address,
            base_amount=self.config.base_amount,
            quote_amount=self.config.quote_amount,
            position_refresh_interval=self.config.position_refresh_interval,
            min_fee_apr_pct=self.config.min_fee_apr_pct,
            min_fee_apr_window_seconds=self.config.min_fee_apr_window_seconds,
            max_duration_seconds=self.config.max_duration_seconds,
            slippage_pct=self.config.slippage_pct,
            keep_position=self.config.keep_position,
        )

    async def update_processed_data(self):
        """No external data needed - LPAmmExecutor reads pool price itself.

        Used once, on this controller instance's first tick, to check the pool for a
        position already open there (e.g. left by a previous session before a
        restart) before determine_executor_actions can create a fresh executor on
        top of it. A failed read is retried on the next tick rather than being
        treated as proof the pool is empty - determine_executor_actions blocks
        creation until this has actually succeeded once.
        """
        if self._startup_position_check_done:
            return
        try:
            connector = self.market_data_provider.get_connector(self.config.connector_name)
            dex_name, trading_type = parse_provider(self.config.lp_provider)
            positions = await connector.get_user_positions(
                dex_name=dex_name, trading_type=trading_type, pool_address=self.config.pool_address,
            )
        except Exception as e:
            self.logger().warning(
                f"Could not check pool {self.config.pool_address} for an existing position: {e} - will retry."
            )
            return
        self._startup_position_check_done = True
        has_existing_position = any(
            info.positions or Decimal(str(getattr(info, "lp_token_amount", 0) or 0)) > 0
            for info in positions
        )
        if has_existing_position:
            self._orphaned_position_address = self.config.pool_address
            self.logger().error(
                f"Found a position already open in pool {self.config.pool_address} on startup "
                "(likely left by a previous session) - halting new position creation until it "
                "is closed or recovered manually."
            )

    def to_format_status(self) -> List[str]:
        status = []
        box_width = 100

        status.append("+" + "-" * box_width + "+")
        header = f"| LP AMM Rebalancer: {self.config.trading_pair} on {self.config.connector_name}"
        status.append(header + " " * (box_width - len(header) + 1) + "|")
        status.append("+" + "-" * box_width + "+")

        line = f"| Pool: {self.config.pool_address} | LP: {self.config.lp_provider}"
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        line = (f"| Config: base={self.config.base_amount}, quote={self.config.quote_amount}, "
                f"min_fee_apr_pct={self.config.min_fee_apr_pct}, "
                f"max_duration_seconds={self.config.max_duration_seconds}, "
                f"reopen_after_close={self.config.reopen_after_close}")
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        status.append("|" + " " * box_width + "|")

        if self._orphaned_position_address:
            line = f"| HALTED: orphaned position {self._orphaned_position_address} needs manual recovery"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        if self._halted_preflight_failures:
            line = (f"| HALTED: {self._consecutive_preflight_failures} consecutive position-creation "
                    "failures - fix the issue and restart")
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        executor = self.active_executor() or self.get_tracked_executor()
        if executor and not executor.is_done:
            custom = executor.custom_info
            line = f"| Position: {custom.get('position_nft_address') or '(fungible LP share)'}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            base_amount = Decimal(str(custom.get("base_amount", 0)))
            quote_amount = Decimal(str(custom.get("quote_amount", 0)))
            total_value_quote = Decimal(str(custom.get("total_value_quote", 0)))
            line = f"| Assets: {float(base_amount):.6f} base + {float(quote_amount):.6f} quote = {float(total_value_quote):.4f} quote"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            fees_earned_quote = Decimal(str(custom.get("fees_earned_quote", 0)))
            fee_apr_pct = custom.get("fee_apr_pct")
            line = f"| Fees earned: {float(fees_earned_quote):.6f} quote | Fee APR: {fee_apr_pct}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

            line = f"| State: {custom.get('state', 'UNKNOWN')}"
            status.append(line + " " * (box_width - len(line) + 1) + "|")
        else:
            line = "| Position: None"
            status.append(line + " " * (box_width - len(line) + 1) + "|")

        status.append("|" + " " * box_width + "|")
        closed = [e for e in self.executors_info
                  if e.is_done and getattr(e.config, "type", None) == "lp_amm_executor"]
        line = (f"| Closed positions: {len(closed)} | "
                f"Position hold: base={self._position_hold_base:+}, quote={self._position_hold_quote:+}")
        status.append(line + " " * (box_width - len(line) + 1) + "|")

        status.append("+" + "-" * box_width + "+")
        return status
