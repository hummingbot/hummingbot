import logging
from decimal import Decimal
from typing import Dict, Optional, Set

from hummingbot.connector.gateway.gateway import AMMPoolInfo
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.gateway_utils import (
    is_slippage_failure,
    next_slippage_pct,
    parse_provider,
    validate_and_normalize_connector,
)
from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import (
    LPAmmExecutorConfig,
    LPAmmExecutorState,
    LPAmmExecutorStates,
)
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder

# Default native currency fallback when connector doesn't have _native_currency set
DEFAULT_NATIVE_CURRENCY = "SOL"


class LPAmmExecutor(ExecutorBase):
    """
    Executor for a single full-range constant-product AMM LP position lifecycle.

    - Opens position on start (direct await, no events), scoped first to one
      NFT-backed AMM connector (e.g. Meteora DAMM v2).
    - Monitors fees earned, impermanent loss and realized fee APR against the
      pool's own reported price - there is no price range to track.
    - Closes when min_fee_apr_pct or max_duration_seconds is crossed, or when
      stopped early.

    Calls the existing connector-layer AMMPoolInfo/AMMPositionInfo/
    AMMPositionDetail and add/remove-liquidity routes unchanged - no connector
    changes are needed for this executor.
    """
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        strategy: StrategyV2Base,
        config: LPAmmExecutorConfig,
        update_interval: float = 1.0,
        max_retries: int = 10,
    ):
        connectors = [config.connector_name]
        super().__init__(strategy, connectors, config, update_interval, max_retries=max_retries)
        self.config: LPAmmExecutorConfig = config
        self._max_retries = max_retries
        self.lp_position_state = LPAmmExecutorState()
        self._pool_info: Optional[AMMPoolInfo] = None
        # One warning, not one per tick, when the pool reports no fee rate and the volume
        # this position generated therefore cannot be derived. See filled_amount_quote.
        self._warned_missing_fee_pct = False
        self._current_price: Optional[Decimal] = None
        self._max_retries_reached = False
        # Same slippage-ramp contract as LPExecutor's: starts at the configured value,
        # widens only on a failure Gateway attributed to slippage, resets at each phase.
        self._slippage_pct: Decimal = config.slippage_pct
        # Consecutive definitive "position does not exist" reads while monitoring;
        # guards against a single lagging RPC node being read as an external close.
        self._position_not_found_count: int = 0
        self._last_position_refresh_timestamp: Optional[float] = None
        # Backoff between close attempts so a burst of instant transport failures
        # cannot burn the whole retry budget in seconds.
        self._close_backoff_until: float = 0.0
        # Why a POSITION_HOLD terminal was involuntary (e.g. "close_retries_exhausted");
        # None for voluntary holds (keep_position=True stops).
        self._hold_reason: Optional[str] = None
        # early_stop() arrived while the create was in flight: let the create resolve,
        # then route straight to CLOSING.
        self._close_after_open: bool = False
        self.lp_dex_name, self.lp_trading_type = parse_provider(config.lp_provider)

    def _validate_and_normalize_connector(self, connector_name: str) -> Optional[str]:
        normalized, success = validate_and_normalize_connector(
            connector_name, "amm", self.logger().error
        )
        if not success:
            self.close_type = CloseType.FAILED
            self.stop()
            return None
        return normalized

    async def on_start(self):
        await super().on_start()
        self.logger().info(
            f"Using LP provider: {self.config.lp_provider} "
            f"(dex={self.lp_dex_name}, type={self.lp_trading_type})"
        )

    async def validate_sufficient_balance(self):
        # LP connector handles balance validation during add_liquidity.
        pass

    async def control_task(self):
        current_time = self._strategy.current_timestamp

        if self.lp_position_state.position_opened:
            if self._is_position_refresh_due(current_time):
                self._last_position_refresh_timestamp = current_time
                await self._update_position_info()
        else:
            await self.update_pool_info()

        self.lp_position_state.update_state()

        match self.lp_position_state.state:
            case LPAmmExecutorStates.NOT_ACTIVE:
                self.lp_position_state.state = LPAmmExecutorStates.OPENING
                await self._create_position()

            case LPAmmExecutorStates.OPENING:
                await self._create_position()

            case LPAmmExecutorStates.CLOSING:
                await self._close_position()

            case LPAmmExecutorStates.FAILED:
                if self.close_type is None:
                    self.close_type = CloseType.FAILED
                self.stop()

            case LPAmmExecutorStates.ACTIVE:
                self._check_exit_triggers(current_time)

            case LPAmmExecutorStates.COMPLETE:
                self.stop()

    def _is_position_refresh_due(self, current_time: float) -> bool:
        last_refresh = self._last_position_refresh_timestamp
        return (
            last_refresh is None
            or current_time < last_refresh
            or current_time - last_refresh >= self.config.position_refresh_interval
        )

    def _check_exit_triggers(self, current_time: float):
        """Close the position once an exit trigger fires, in place of a price range."""
        if self._current_price is None or self.lp_position_state.add_timestamp is None:
            return

        elapsed = current_time - self.lp_position_state.add_timestamp

        if self.config.max_duration_seconds is not None and elapsed >= self.config.max_duration_seconds:
            self.logger().info(
                f"max_duration_seconds ({self.config.max_duration_seconds}) reached after "
                f"{elapsed:.0f}s, closing"
            )
            self._trigger_close()
            return

        if self.config.min_fee_apr_pct is not None and elapsed >= self.config.min_fee_apr_window_seconds:
            fee_apr = self.lp_position_state.fee_apr_pct(self._current_price, current_time)
            if fee_apr is not None and fee_apr < self.config.min_fee_apr_pct:
                self.logger().info(
                    f"Fee APR {fee_apr:.4f}% fell below min_fee_apr_pct "
                    f"({self.config.min_fee_apr_pct}%), closing"
                )
                self._trigger_close()

    def _trigger_close(self):
        self.close_type = CloseType.POSITION_HOLD if self.config.keep_position else CloseType.EARLY_STOP
        self.lp_position_state.state = LPAmmExecutorStates.CLOSING

    def _widen_slippage(self, error: Exception) -> bool:
        """Widen the tolerance for the next attempt, if this failure was slippage."""
        if not is_slippage_failure(error):
            return False

        widened = next_slippage_pct(
            self._slippage_pct, self.config.slippage_multiplier, self.config.max_slippage_pct
        )
        if widened is None:
            self.logger().warning(
                f"Slippage failure at {self._slippage_pct}%, which is max_slippage_pct "
                f"({self.config.max_slippage_pct}%). Not widening further."
            )
            return False

        self.logger().info(
            f"Slippage failure at {self._slippage_pct}%; retrying at {widened}% "
            f"(x{self.config.slippage_multiplier}, ceiling {self.config.max_slippage_pct}%)."
        )
        self._slippage_pct = widened
        return True

    def _reset_slippage(self):
        if self._slippage_pct != self.config.slippage_pct:
            self.logger().info(f"Resetting slippage to {self.config.slippage_pct}% for the next phase.")
        self._slippage_pct = self.config.slippage_pct

    async def _existing_nft_position_addresses(self, connector) -> Set[str]:
        """Snapshot the wallet's NFT position addresses in this pool before opening.

        Used to identify which position add_liquidity just created on an
        NFT-backed AMM, by diffing against the addresses seen right after.
        """
        try:
            positions = await connector.get_user_positions(
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                pool_address=self.config.pool_address,
            )
        except Exception as e:
            self.logger().warning(f"Could not snapshot existing positions in {self.config.pool_address}: {e}")
            return set()
        addresses = set()
        for info in positions:
            for detail in (info.positions or []):
                addresses.add(detail.position_address)
        return addresses

    async def _create_position(self):
        """Create position by directly awaiting the gateway operation."""
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._handle_create_failure(ValueError(f"Connector {self.config.connector_name} not found"))
            return

        price = self._current_price if self._current_price else Decimal("0")
        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_open_order = TrackedOrder(order_id=order_id)

        try:
            before_addresses = await self._existing_nft_position_addresses(connector)

            self.logger().info(f"Calling gateway to add AMM liquidity with order_id={order_id}")
            signature = await connector._amm_add_liquidity(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                price=float(price),
                base_token_amount=float(self.config.base_amount),
                quote_token_amount=float(self.config.quote_amount),
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                slippage_pct=float(self._slippage_pct),
                max_retries=self._max_retries,
            )

            self.lp_position_state.active_open_order = None
            self.lp_position_state.open_tx_hash = signature
            self._reset_slippage()

            try:
                position_info = await connector.get_position_info_fresh(
                    trading_pair=self.config.trading_pair,
                    dex_name=self.lp_dex_name,
                    trading_type=self.lp_trading_type,
                    position_address=self.config.pool_address,
                )
            except Exception as info_error:
                self.logger().warning(f"Position info fetch after create failed: {info_error}")
                position_info = None

            nft_address = None
            base_amount = self.config.base_amount
            quote_amount = self.config.quote_amount
            current_price = price

            if position_info is not None:
                current_price = Decimal(str(position_info.price))
                details = position_info.positions
                if details:
                    new_addresses = {d.position_address for d in details} - before_addresses
                    if len(new_addresses) != 1:
                        self._handle_create_failure(ValueError(
                            f"Open transaction {signature} CONFIRMED on-chain but the opened NFT "
                            f"position in pool {self.config.pool_address} could not be identified "
                            f"({len(new_addresses)} new positions appeared, expected 1). A position "
                            "is likely LIVE and unmanaged - reconcile this wallet by hand."
                        ))
                        return
                    nft_address = next(iter(new_addresses))
                    detail = next(d for d in details if d.position_address == nft_address)
                    base_amount = Decimal(str(detail.base_token_amount))
                    quote_amount = Decimal(str(detail.quote_token_amount))
                else:
                    # Fungible-LP pool: no per-position breakdown, the pool address
                    # alone identifies the wallet's whole holding.
                    base_amount = Decimal(str(position_info.base_token_amount))
                    quote_amount = Decimal(str(position_info.quote_token_amount))
            else:
                self.logger().warning(
                    "Position info fetch failed after a confirmed open: using config amounts as a "
                    "fallback and leaving the NFT position address unresolved."
                )
                self.lp_position_state.open_data_unavailable = True

            self.lp_position_state.position_opened = True
            self.lp_position_state.position_nft_address = nft_address
            self.lp_position_state.base_amount = base_amount
            self.lp_position_state.quote_amount = quote_amount
            self.lp_position_state.initial_base_amount = base_amount
            self.lp_position_state.initial_quote_amount = quote_amount
            self.lp_position_state.add_price = current_price
            self.lp_position_state.add_timestamp = self._strategy.current_timestamp
            self._current_price = current_price

            self.logger().info(
                f"AMM position opened in pool {self.config.pool_address}"
                f"{f' (nft {nft_address})' if nft_address else ''}: "
                f"base={base_amount}, quote={quote_amount}"
            )

            if self._close_after_open:
                self.logger().info("Create resolved after early_stop: closing immediately.")
                self.lp_position_state.state = LPAmmExecutorStates.CLOSING
                return

            self.lp_position_state.update_state()

        except Exception as e:
            self._handle_create_failure(e)

    def _handle_create_failure(self, error: Exception):
        """Handle position creation failure.

        Retrying the open is only safe for a slippage failure: Gateway raises
        it either from the pre-flight simulation (nothing sent) or from a
        transaction that landed and reverted (nothing deposited), so there is
        no position to deposit a second one on top of.
        """
        self.lp_position_state.active_open_order = None

        if not self.lp_position_state.position_opened and self._widen_slippage(error):
            self._current_retries += 1
            self.logger().warning(
                f"Position creation failed on slippage ({self._current_retries}/{self._max_retries} "
                f"retries used): {error}. Retrying at {self._slippage_pct}%."
            )
            self.lp_position_state.state = LPAmmExecutorStates.OPENING
            return

        if self.lp_position_state.position_opened:
            self.logger().error(
                f"Position creation failed after the position was opened in pool "
                f"{self.config.pool_address} ({self.config.trading_pair}): {error}. "
                "Closing it to recover the funds."
            )
            self.close_type = CloseType.FAILED
            self.lp_position_state.state = LPAmmExecutorStates.CLOSING
            return

        self.logger().error(f"Position creation failed: {error}")
        self.lp_position_state.state = LPAmmExecutorStates.FAILED

    async def _update_position_info(self):
        """Fetch current position info from the connector to update amounts."""
        if not self.lp_position_state.position_opened:
            return

        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            return

        try:
            position_info = await connector.get_position_info_fresh(
                trading_pair=self.config.trading_pair,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                position_address=self.config.pool_address,
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "position closed" in error_msg or "position not found" in error_msg or "position does not exist" in error_msg:
                self._register_position_miss()
            else:
                self.logger().warning(f"Error fetching position info: {e}")
            return

        if position_info is None:
            self._register_position_miss()
            return

        self._current_price = Decimal(str(position_info.price))

        if self.lp_position_state.position_nft_address:
            detail = next(
                (d for d in (position_info.positions or [])
                 if d.position_address == self.lp_position_state.position_nft_address),
                None,
            )
            if detail is None:
                self._register_position_miss()
                return
            self.lp_position_state.base_amount = Decimal(str(detail.base_token_amount))
            self.lp_position_state.quote_amount = Decimal(str(detail.quote_token_amount))
        else:
            self.lp_position_state.base_amount = Decimal(str(position_info.base_token_amount))
            self.lp_position_state.quote_amount = Decimal(str(position_info.quote_token_amount))

        self._position_not_found_count = 0

    def _register_position_miss(self):
        """Count a definitive "position gone" read; three in a row ends the position.

        A single miss is never proof - a lagging RPC node's 404 would otherwise
        declare a freshly funded position closed.
        """
        self._position_not_found_count += 1
        if self._position_not_found_count >= 3:
            self.logger().info(
                f"Position in pool {self.config.pool_address} no longer exists on-chain "
                "(closed externally or by a prior attempt) - marking complete"
            )
            if self.close_type is None:
                self.close_type = CloseType.POSITION_HOLD if self.config.keep_position else CloseType.EARLY_STOP
            self._handle_position_gone()

    def _handle_position_gone(self):
        """The position is definitively absent on-chain: a prior close attempt
        landed, or it was closed externally."""
        current_price = self._current_price if self._current_price else Decimal("0")
        if self.close_type == CloseType.POSITION_HOLD:
            self._store_net_trade_from_withdrawal(current_price)

        self.lp_position_state.active_close_order = None
        self.lp_position_state.position_opened = False
        self.lp_position_state.position_nft_address = None
        self.lp_position_state.state = LPAmmExecutorStates.COMPLETE

    async def _close_position(self):
        """Close position by directly awaiting the gateway operation."""
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._handle_close_failure(ValueError(f"Connector {self.config.connector_name} not found"))
            return

        if self._strategy.current_timestamp < self._close_backoff_until:
            return

        # Verify the position still exists before trying to close (handles a
        # timeout-but-succeeded prior attempt). Only trusted on an NFT-backed
        # position, since a fungible-LP read has no "not found" signal to act on.
        if self.lp_position_state.position_nft_address:
            try:
                position_info = await connector.get_position_info_fresh(
                    trading_pair=self.config.trading_pair,
                    dex_name=self.lp_dex_name,
                    trading_type=self.lp_trading_type,
                    position_address=self.config.pool_address,
                )
            except Exception as e:
                error_msg = str(e).lower()
                position_info = None if ("position closed" in error_msg or "position not found" in error_msg) else False
            gone = position_info is None or (
                position_info is not False and
                not any(d.position_address == self.lp_position_state.position_nft_address
                        for d in (position_info.positions or []))
            )
            if gone:
                self._position_not_found_count += 1
                if self._position_not_found_count >= 3:
                    self.logger().info(
                        f"Position {self.lp_position_state.position_nft_address} definitively absent "
                        f"({self._position_not_found_count} consecutive misses) - already closed"
                    )
                    self._handle_position_gone()
                    return
                self.logger().warning(
                    f"Pre-flight miss {self._position_not_found_count}/3 for "
                    f"{self.lp_position_state.position_nft_address}; not closing this tick"
                )
                return
            if position_info is not False:
                self._position_not_found_count = 0

        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_close_order = TrackedOrder(order_id=order_id)

        try:
            # One gateway request per attempt (max_retries=0): this CLOSING loop owns
            # the close retries, same contract as LPExecutor's.
            signature = await connector._amm_remove_liquidity(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                percentage=100.0,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                position_address=self.lp_position_state.position_nft_address,
                max_retries=0,
            )

            self.logger().info(f"Position close confirmed, signature={signature}")
            # _amm_remove_liquidity reports neither the removed amounts nor a close
            # tx fee back to the caller (unlike the CLMM close, whose response data
            # carries both) - the last amounts this executor read before closing are
            # the best available accounting for what came out, since removing 100%
            # returns what was last observed.
            self.lp_position_state.close_tx_hash = signature
            self.lp_position_state.active_close_order = None

            current_price = self._current_price if self._current_price else Decimal("0")
            if self.close_type == CloseType.POSITION_HOLD:
                self._store_net_trade_from_withdrawal(current_price)

            self.lp_position_state.position_opened = False
            self.lp_position_state.position_nft_address = None
            self.lp_position_state.state = LPAmmExecutorStates.COMPLETE

        except Exception as e:
            self._handle_close_failure(e)

    def _handle_close_failure(self, error: Exception):
        """Handle position close failure.

        The position is still open on-chain, so going terminal here would
        strand it. Count the attempt, arm the backoff, and stay in CLOSING -
        control_task re-enters _close_position on the next tick. Termination
        on exhaustion is decided by evaluate_max_retries.
        """
        self._current_retries += 1
        self.lp_position_state.active_close_order = None
        self._widen_slippage(error)

        if self._current_retries > self._max_retries:
            self.logger().warning(f"Position close attempt failed: {error}. Retry budget exhausted.")
            return

        backoff = min(30.0, 2.0 ** self._current_retries)
        self._close_backoff_until = self._strategy.current_timestamp + backoff
        self.logger().warning(
            f"Position close attempt failed ({self._current_retries}/{self._max_retries} retries used): "
            f"{error}. Rebuilding with fresh state in {backoff:.0f}s."
        )

    def evaluate_max_retries(self):
        """Terminate when the close-retry budget is exhausted.

        A position still on-chain is residual exposure and ends as an
        involuntary POSITION_HOLD, reserving FAILED for executors with
        nothing left behind - same family contract as LPExecutor's.
        """
        if self._current_retries <= self._max_retries:
            return
        self._max_retries_reached = True
        if self.lp_position_state.position_opened:
            self._hold_reason = "close_retries_exhausted"
            self._record_unclosed_position_marker()
            self.close_type = CloseType.POSITION_HOLD
            self.logger().error(
                f"Position close failed after {self._current_retries} attempts: position in pool "
                f"{self.config.pool_address} ({self.config.trading_pair}) is still open on-chain. "
                "Terminating as an involuntary POSITION_HOLD (hold_reason=close_retries_exhausted) - "
                "close it via the gateway and resolve the orphan record."
            )
        else:
            self.close_type = CloseType.FAILED
            self.logger().error(
                f"Retry budget exhausted after {self._current_retries} attempts with no position "
                "on-chain - terminating as FAILED."
            )
        self.stop()

    def _record_unclosed_position_marker(self):
        """Append a zero-amount marker order carrying the unclosed position's identity.

        A live on-chain position cannot be booked as spot amounts - the tokens
        are in the pool, not the wallet - but an empty held_position_orders
        would make the POSITION_HOLD invisible to the hold store.
        """
        self._held_position_orders.append({
            "client_order_id": f"{self.config.id}-unclosed-lp",
            "trading_pair": self.config.trading_pair,
            "trade_type": "BUY",  # dummy; zero amounts never reach accounting
            "price": float(self._current_price) if self._current_price else 0.0,
            "executed_amount_base": 0.0,
            "executed_amount_quote": 0.0,
            "cumulative_fee_paid_quote": 0.0,
            "lp_source": True,
            "lp_unclosed_position": True,
            "pool_address": self.config.pool_address,
            "position_nft_address": self.lp_position_state.position_nft_address,
        })

    def early_stop(self, keep_position: bool = True):
        """Stop executor - transitions to CLOSING state.

        Args:
            keep_position: If True, after closing the LP position on-chain,
                the net token change is tracked as a spot position.
        """
        self._status = RunnableStatus.SHUTTING_DOWN
        self.close_type = CloseType.POSITION_HOLD if keep_position else CloseType.EARLY_STOP

        if self.lp_position_state.state == LPAmmExecutorStates.ACTIVE:
            self.lp_position_state.state = LPAmmExecutorStates.CLOSING
        elif self.lp_position_state.state == LPAmmExecutorStates.OPENING:
            # The create is in flight and its transaction may LAND - killing the
            # state here would strand a live, funded position behind a FAILED
            # terminal. Let the create resolve; its success tail routes to CLOSING.
            self._close_after_open = True
            self.logger().info(
                "early_stop during OPENING: waiting for the in-flight create to resolve, then closing."
            )
        elif self.lp_position_state.state == LPAmmExecutorStates.NOT_ACTIVE:
            self.lp_position_state.state = LPAmmExecutorStates.COMPLETE

    def _get_native_to_quote_rate(self) -> Decimal:
        """Conversion rate from native currency (e.g. SOL) to pool quote currency,
        used to convert transaction fees (paid in native currency) to quote."""
        connector = self.connectors.get(self.config.connector_name)
        native_currency = getattr(connector, '_native_currency', DEFAULT_NATIVE_CURRENCY) or DEFAULT_NATIVE_CURRENCY
        _, quote_token = split_hb_trading_pair(self.config.trading_pair)

        if native_currency == quote_token:
            return Decimal("1")

        try:
            rate = RateOracle.get_instance().get_pair_rate(f"{native_currency}-{quote_token}")
            if rate is not None and rate > 0:
                return rate
        except Exception as e:
            self.logger().debug(f"Could not get rate for {native_currency}-{quote_token}: {e}")

        return Decimal("1")

    def _store_net_trade_from_withdrawal(self, mid_price: Decimal):
        """Record the net token change of the round trip as a single held order.

        The executor owns the round trip, not the whole withdrawn balance: what
        is reported is the change relative to the initial deposit (including
        fees baked into the reserves), not the total removed.
        """
        net_base = self.lp_position_state.base_amount - self.lp_position_state.initial_base_amount
        net_quote = self.lp_position_state.quote_amount - self.lp_position_state.initial_quote_amount
        tx_fee_quote = self.lp_position_state.tx_fee * self._get_native_to_quote_rate()
        threshold = Decimal("0.0001")
        order_id = self.lp_position_state.close_tx_hash or f"{self.config.id}-close"

        if abs(net_base) < threshold and abs(net_quote) < threshold:
            self._held_position_orders.append({
                "client_order_id": order_id,
                "trade_type": "BUY",  # dummy, won't affect P&L with 0 amounts
                "price": float(mid_price),
                "executed_amount_base": 0.0,
                "executed_amount_quote": 0.0,
                "cumulative_fee_paid_quote": float(tx_fee_quote),
                "lp_source": True,
                "lp_net_trade": True,
            })
            return

        if net_base > 0:
            trade_type = "BUY"
            amount_base = float(net_base)
        else:
            trade_type = "SELL"
            amount_base = float(abs(net_base))
        amount_quote = float(abs(net_quote)) if abs(net_quote) > threshold else amount_base * float(mid_price)
        price = amount_quote / amount_base if amount_base > 0 else float(mid_price)

        self._held_position_orders.append({
            "client_order_id": order_id,
            "trading_pair": self.config.trading_pair,
            "trade_type": trade_type,
            "price": price,
            "amount": amount_base,
            "executed_amount_base": amount_base,
            "executed_amount_quote": amount_quote,
            "cumulative_fee_paid_quote": float(tx_fee_quote),
            "lp_source": True,
            "lp_net_trade": True,
        })

    @property
    def filled_amount_base(self) -> Decimal:
        return self.lp_position_state.base_amount

    @property
    def filled_amount_quote(self) -> Decimal:
        """The swap volume that flowed through this position, in quote.

        Same derivation as LPExecutor's: fees are a fixed fraction of the
        volume that paid them, so volume = fees_earned_in_quote / fee_rate.
        Returns 0 when the pool's fee rate is unknown, which is a missing
        measurement rather than an absence of volume.
        """
        if self._pool_info is None or self._current_price is None:
            return Decimal("0")

        fee_pct = getattr(self._pool_info, "fee_pct", None)
        if not fee_pct or Decimal(str(fee_pct)) <= 0:
            if not self._warned_missing_fee_pct:
                self._warned_missing_fee_pct = True
                self.logger().warning(
                    f"Pool {self.config.pool_address} reports a fee rate of {fee_pct!r}, so the "
                    "volume this position generated cannot be derived from its fees. "
                    "Reporting 0 volume."
                )
            return Decimal("0")

        fees_quote = self.lp_position_state.fees_earned_quote(self._current_price)
        if fees_quote <= 0:
            return Decimal("0")

        return fees_quote / (Decimal(str(fee_pct)) / Decimal("100"))

    def get_net_pnl_quote(self) -> Decimal:
        """
        Net P&L in pool quote currency: current redeemable value (which already
        includes fee growth) minus the initial deposit's value, minus tx fees.
        """
        if self._current_price is None or self._current_price == 0:
            return Decimal("0")
        if self.lp_position_state.state == LPAmmExecutorStates.FAILED and not self.lp_position_state.position_opened:
            return Decimal("0")

        current_value = self.lp_position_state.current_value_quote(self._current_price)
        if self.lp_position_state.add_price > 0:
            initial_value = self.lp_position_state.held_value_quote(self.lp_position_state.add_price)
        else:
            initial_value = current_value
        tx_fee_quote = self.lp_position_state.tx_fee * self._get_native_to_quote_rate()
        return current_value - initial_value - tx_fee_quote

    def get_net_pnl_pct(self) -> Decimal:
        pnl_quote = self.get_net_pnl_quote()
        if pnl_quote == Decimal("0") or self.lp_position_state.add_price <= 0:
            return Decimal("0")
        initial_value = self.lp_position_state.held_value_quote(self.lp_position_state.add_price)
        if initial_value == Decimal("0"):
            return Decimal("0")
        return pnl_quote / initial_value

    def get_cum_fees_quote(self) -> Decimal:
        """Cumulative transaction/gas costs in quote currency (NOT LP fees earned)."""
        return self.lp_position_state.tx_fee * self._get_native_to_quote_rate()

    def get_custom_info(self) -> Dict:
        """Report LP position state to controller."""
        price = self._current_price
        current_time = self._strategy.current_timestamp
        fee_apr = self.lp_position_state.fee_apr_pct(price, current_time) if price else None

        return {
            "state": self.lp_position_state.state.value,
            "pool_address": self.config.pool_address,
            "position_nft_address": self.lp_position_state.position_nft_address,
            "current_price": float(price) if price else None,
            "base_amount": float(self.lp_position_state.base_amount),
            "quote_amount": float(self.lp_position_state.quote_amount),
            "initial_base_amount": float(self.lp_position_state.initial_base_amount),
            "initial_quote_amount": float(self.lp_position_state.initial_quote_amount),
            "fees_earned_quote": float(self.lp_position_state.fees_earned_quote(price)) if price else 0.0,
            "impermanent_loss_quote": float(self.lp_position_state.impermanent_loss_quote(price)) if price else 0.0,
            "fee_apr_pct": float(fee_apr) if fee_apr is not None else None,
            "total_value_quote": float(self.lp_position_state.current_value_quote(price)) if price else 0.0,
            "unrealized_pnl_quote": float(self.get_net_pnl_quote()),
            "tx_fee": float(self.lp_position_state.tx_fee),
            "filled_amount_base": float(self.lp_position_state.base_amount),
            "filled_amount_quote": float(self.lp_position_state.quote_amount),
            "held_position_orders": self._held_position_orders,
            "current_retries": self._current_retries,
            "max_retries": self._max_retries,
            "max_retries_reached": self._max_retries_reached,
            "slippage_pct": float(self._slippage_pct),
            "max_slippage_pct": float(self.config.max_slippage_pct),
            "hold_reason": self._hold_reason,
            "open_data_unavailable": self.lp_position_state.open_data_unavailable,
            "close_data_unavailable": self.lp_position_state.close_data_unavailable,
        }

    async def update_pool_info(self):
        """Fetch and store current pool info."""
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            return

        try:
            self._pool_info = await connector.get_pool_info_by_address(
                self.config.pool_address,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
            )
            if self._pool_info:
                self._current_price = Decimal(str(self._pool_info.price))
        except Exception as e:
            self.logger().warning(f"Error fetching pool info: {e}")
