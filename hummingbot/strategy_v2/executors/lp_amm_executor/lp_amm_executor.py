import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from hummingbot.connector.gateway.gateway import AMMPoolInfo
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
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
        # Close-out swap attempts (each failure re-places with a fresh quote), same
        # contract as LPExecutor's.
        self._swap_not_found_count: int = 0
        self._swap_failure_count: int = 0
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

        # Resolve swap_provider up front when the config already expects to unwind,
        # so a missing provider surfaces at start instead of mid-close-out.
        if not self.config.keep_position:
            await self._resolve_swap_provider()

    async def _resolve_swap_provider(self) -> bool:
        """Fill in swap_provider from the network default if it is not set.

        Also called lazily from the close-out path: early_stop(keep_position=False)
        can unwind an executor whose config said keep_position=True, which never
        resolved a provider at start.

        Returns True if a provider is available.
        """
        if self.config.swap_provider:
            return True

        gateway = GatewayHttpClient.get_instance()
        default_provider = await gateway.get_default_swap_provider(self.config.connector_name)
        if default_provider:
            # The network default comes straight from Gateway's config, which is not
            # covered by LPAmmExecutorConfig's validator — reject an untyped one here
            # instead of letting it become a 400 mid close-out swap.
            if "/" not in default_provider:
                self.logger().error(
                    f"Network default swap provider '{default_provider}' for "
                    f"{self.config.connector_name} is not in 'name/type' form "
                    "(e.g. 'jupiter/router'). Fix swapProvider in the Gateway network config."
                )
                return False
            self.config = self.config.model_copy(update={'swap_provider': default_provider})
            self.logger().info(f"Using network default swap provider: {default_provider}")
            return True

        self.logger().warning(
            f"No swap provider found for {self.config.connector_name}. "
            "Close-out swaps will not be available."
        )
        return False

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

            case LPAmmExecutorStates.SWAPPING:
                # Close-out swap in progress (keep_position=False)
                await self._execute_closeout_swap()

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

    async def _snapshot_before_add(self, connector) -> Tuple[Set[str], Optional[Decimal]]:
        """Snapshot the wallet's position in this pool before depositing.

        Used to isolate what add_liquidity just created from whatever the wallet
        already held in the pool: by NFT address diff on an NFT-backed AMM, or by
        LP-token balance delta on a fungible-LP one (no NFT breakdown) - otherwise
        this executor would adopt the wallet's whole fungible-LP holding as its own
        and later withdraw all of it, including any other liquidity sharing the pool.
        """
        try:
            positions = await connector.get_user_positions(
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                pool_address=self.config.pool_address,
            )
        except Exception as e:
            self.logger().warning(f"Could not snapshot existing positions in {self.config.pool_address}: {e}")
            return set(), None
        addresses = set()
        lp_token_amount = Decimal("0")
        for info in positions:
            details = info.positions or []
            for detail in details:
                addresses.add(detail.position_address)
            if not details:
                lp_token_amount += Decimal(str(getattr(info, "lp_token_amount", 0) or 0))
        return addresses, lp_token_amount

    async def _pool_address_matches_config(self, connector) -> bool:
        """Reject a deposit/withdrawal the connector would route to a different pool
        than the one this executor is configured to watch.

        _amm_add_liquidity/_amm_remove_liquidity each independently resolve a pool
        from the trading pair alone; if the wallet has liquidity in more than one
        pool for the same pair, that resolution can silently disagree with
        config.pool_address.
        """
        try:
            discovered = await connector.get_pool_address(
                self.config.trading_pair, dex_name=self.lp_dex_name, trading_type=self.lp_trading_type,
            )
        except Exception as e:
            self.logger().warning(f"Could not verify pool address for {self.config.trading_pair}: {e}")
            return True
        if discovered and discovered != self.config.pool_address:
            self.logger().error(
                f"Configured pool {self.config.pool_address} for {self.config.trading_pair} does not match "
                f"the pool {discovered} the connector resolved for that pair - refusing to risk funds on the "
                "wrong pool."
            )
            return False
        return True

    async def _create_position(self):
        """Create position by directly awaiting the gateway operation."""
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._handle_create_failure(ValueError(f"Connector {self.config.connector_name} not found"))
            return

        if not await self._pool_address_matches_config(connector):
            self._handle_create_failure(ValueError(
                f"Pool mismatch for {self.config.trading_pair}: configured {self.config.pool_address}"
            ))
            return

        price = self._current_price if self._current_price else Decimal("0")
        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_open_order = TrackedOrder(order_id=order_id)

        try:
            before_addresses, before_lp_tokens = await self._snapshot_before_add(connector)

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

            if not signature:
                # The connector's failure contract: a caught transaction error is
                # recorded on the order and swallowed into None, not re-raised.
                # Treating that as a signature would book a deposit that never landed.
                self._handle_create_failure(ValueError(
                    f"Add liquidity for {self.config.trading_pair} returned no transaction signature"
                ))
                return

            self.lp_position_state.active_open_order = None
            self.lp_position_state.open_tx_hash = signature
            self._reset_slippage()

            position_info = None
            for attempt in range(3):
                try:
                    position_info = await connector.get_position_info_fresh(
                        trading_pair=self.config.trading_pair,
                        dex_name=self.lp_dex_name,
                        trading_type=self.lp_trading_type,
                        position_address=self.config.pool_address,
                    )
                    break
                except Exception as info_error:
                    self.logger().warning(
                        f"Position info fetch after create failed (attempt {attempt + 1}/3): {info_error}"
                    )
                    if attempt < 2:
                        await asyncio.sleep(1.0)

            nft_address = None
            own_lp_token_amount = None
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
                    # Fungible-LP pool: no per-position breakdown. Isolate this
                    # deposit's own share by the LP-token delta, not the wallet's
                    # whole holding - otherwise closing this executor later withdraws
                    # everything the wallet holds in the pool.
                    base_amount = Decimal(str(position_info.base_token_amount))
                    quote_amount = Decimal(str(position_info.quote_token_amount))
                    after_lp_tokens = Decimal(str(getattr(position_info, "lp_token_amount", 0) or 0))
                    if before_lp_tokens is not None:
                        own_lp_token_amount = after_lp_tokens - before_lp_tokens
                    else:
                        self.logger().warning(
                            "Pre-deposit LP-token snapshot was unavailable: this executor cannot isolate "
                            "its own share of a fungible-LP pool and will withdraw the wallet's whole "
                            "balance on close."
                        )
            else:
                self.logger().warning(
                    "Position info fetch failed after a confirmed open: using config amounts as a "
                    "fallback and leaving the NFT position address unresolved."
                )
                self.lp_position_state.open_data_unavailable = True

            self.lp_position_state.position_opened = True
            self.lp_position_state.position_nft_address = nft_address
            self.lp_position_state.own_lp_token_amount = own_lp_token_amount
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
        landed, or it was closed externally. EARLY_STOP still owes the close-out
        swap, since the withdrawn tokens landed in the wallet either way."""
        current_price = self._current_price if self._current_price else Decimal("0")
        if self.close_type == CloseType.POSITION_HOLD:
            self._store_net_trade_from_withdrawal(current_price)

        self.lp_position_state.active_close_order = None
        self.lp_position_state.position_opened = False
        self.lp_position_state.position_nft_address = None

        if self.close_type == CloseType.EARLY_STOP:
            base_diff = self._calculate_net_base_difference()
            if abs(base_diff) > Decimal("0.000001"):
                self.logger().info(
                    f"Close-out swap needed after already-closed reconcile: base_diff={base_diff:.6f}"
                )
                self._reset_slippage()
                self.lp_position_state.state = LPAmmExecutorStates.SWAPPING
                return
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

        if not await self._pool_address_matches_config(connector):
            self._handle_close_failure(ValueError(
                f"Pool mismatch for {self.config.trading_pair}: configured {self.config.pool_address}"
            ))
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

        remove_percentage = 100.0
        if not self.lp_position_state.position_nft_address and self.lp_position_state.own_lp_token_amount is not None:
            # Fungible-LP pool: removing 100% would withdraw whatever else the
            # wallet holds there too. Scale down to this executor's own share of
            # the wallet's current LP-token balance.
            try:
                wallet_position = await connector.get_position_info_fresh(
                    trading_pair=self.config.trading_pair,
                    dex_name=self.lp_dex_name,
                    trading_type=self.lp_trading_type,
                    position_address=self.config.pool_address,
                )
            except Exception as e:
                self._handle_close_failure(e)
                return
            wallet_lp_tokens = (
                Decimal(str(getattr(wallet_position, "lp_token_amount", 0) or 0)) if wallet_position else Decimal("0")
            )
            own_lp_tokens = self.lp_position_state.own_lp_token_amount
            if wallet_lp_tokens <= 0 or own_lp_tokens <= 0:
                self.logger().info(
                    f"Fungible-LP pool {self.config.pool_address} reports no LP-token balance left for "
                    "this executor's own share - treating the position as already gone."
                )
                self._handle_position_gone()
                return
            remove_percentage = min(100.0, float(own_lp_tokens / wallet_lp_tokens * 100))

        order_id = connector.create_market_order_id(TradeType.RANGE, self.config.trading_pair)
        self.lp_position_state.active_close_order = TrackedOrder(order_id=order_id)

        try:
            # One gateway request per attempt (max_retries=0): this CLOSING loop owns
            # the close retries, same contract as LPExecutor's.
            signature = await connector._amm_remove_liquidity(
                trade_type=TradeType.RANGE,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                percentage=remove_percentage,
                dex_name=self.lp_dex_name,
                trading_type=self.lp_trading_type,
                position_address=self.lp_position_state.position_nft_address,
                max_retries=0,
            )

            if not signature:
                # Same swallowed-failure contract as the add side: a caught
                # transaction error is recorded on the order and returns None
                # rather than raising. Treating that as a signature would mark
                # liquidity removed, and still on-chain, as closed.
                self._handle_close_failure(ValueError(
                    f"Remove liquidity for {self.config.trading_pair} returned no transaction signature"
                ))
                return

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

            # Not holding the net means swapping any leftover single-sided balance
            # back to the initial deposit's target. Stated positively, like
            # LPExecutor's, so an unexpected close_type skips the swap rather than
            # firing one nobody asked for.
            if self.close_type == CloseType.EARLY_STOP:
                base_diff = self._calculate_net_base_difference()
                if abs(base_diff) > Decimal("0.000001"):
                    self.logger().info(
                        f"Close-out swap needed: base_diff={base_diff:.6f} "
                        f"(received={self.lp_position_state.base_amount:.6f}, "
                        f"initial={self.lp_position_state.initial_base_amount:.6f})"
                    )
                    # A third phase, and a third chance to start tight.
                    self._reset_slippage()
                    self.lp_position_state.state = LPAmmExecutorStates.SWAPPING
                else:
                    self.logger().info("No close-out swap needed (base amounts match)")
                    self.lp_position_state.state = LPAmmExecutorStates.COMPLETE
            else:
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

    def _calculate_net_base_difference(self) -> Decimal:
        """Net base token difference between what this withdrawal returned and what
        was initially deposited.

        Swapping base back to zero this difference leaves the executor
        position-neutral: quote moves opposite to base through the swap itself, so
        fixing the base side also fixes the quote side. base_amount already carries
        fee growth for a full-range AMM (fees accrue into the reserves, not a
        separate ledger - see LPAmmExecutorState.fees_earned_quote), so unlike
        LPExecutor's version there is no separate fee term to add back in.

        Returns:
            Positive: more base than initially deposited (need to SELL)
            Negative: less base than initially deposited (need to BUY)
            Zero: position is balanced
        """
        return self.lp_position_state.base_amount - self.lp_position_state.initial_base_amount

    async def _execute_closeout_swap(self):
        """Execute the close-out swap back to the initial deposit's base/quote
        balance when keep_position=False. Same SWAPPING contract as LPExecutor's.
        """
        connector = self.connectors.get(self.config.connector_name)
        if connector is None:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._handle_swap_failure(ValueError(f"Connector {self.config.connector_name} not found"))
            return

        if not await self._resolve_swap_provider():
            self.logger().error("No swap_provider configured for close-out swap")
            self._handle_swap_failure(ValueError("No swap_provider configured"))
            return

        # Check if we already have an active swap order
        if self.lp_position_state.active_swap_order is not None:
            order = connector.get_order(self.lp_position_state.active_swap_order.order_id)
            if order is None:
                # Order not found - might have completed or failed
                self._swap_not_found_count += 1
                if self._swap_not_found_count >= 3:
                    self.logger().warning(
                        f"Swap order {self.lp_position_state.active_swap_order.order_id} not found after "
                        f"{self._swap_not_found_count} checks. Assuming completed."
                    )
                    self.lp_position_state.active_swap_order = None
                    self.lp_position_state.state = LPAmmExecutorStates.COMPLETE
                return

            from hummingbot.core.data_type.in_flight_order import OrderState
            if order.current_state == OrderState.FILLED:
                self.logger().info(f"Close-out swap completed: {order.client_order_id}")
                self.lp_position_state.active_swap_order = None
                self.lp_position_state.state = LPAmmExecutorStates.COMPLETE
            elif order.current_state == OrderState.FAILED:
                # Ask the connector what Gateway said: the order tracker records
                # FAILED with no reason, and the slippage ramp cannot act on this leg
                # without knowing whether the failure was a slippage failure at all.
                reason = connector.order_failure_reason(order.client_order_id) or "Swap order failed"
                self.logger().error(f"Close-out swap failed: {order.client_order_id}: {reason}")
                self._handle_swap_failure(ValueError(reason))
            elif order.current_state == OrderState.CANCELED:
                self.logger().warning(f"Close-out swap cancelled: {order.client_order_id}")
                self._handle_swap_failure(ValueError("Swap order cancelled"))
            # Otherwise still pending - wait for next tick
            return

        base_diff = self._calculate_net_base_difference()

        if abs(base_diff) < Decimal("0.000001"):
            # No swap needed
            self.lp_position_state.state = LPAmmExecutorStates.COMPLETE
            return

        # base_diff > 0: received more base than deposited -> SELL excess base
        # base_diff < 0: received less base than deposited -> BUY base to restore
        is_buy = base_diff < 0
        amount = abs(base_diff)
        side = TradeType.BUY if is_buy else TradeType.SELL

        self.logger().info(
            f"Executing close-out swap: {side.name} {amount:.6f} base (diff={base_diff:.6f})"
        )

        try:
            # The executor's own ramped tolerance, so the close-out swap starts as
            # tight as everything else this executor does and widens the same way.
            order_id = connector.place_order(
                is_buy=is_buy,
                trading_pair=self.config.trading_pair,
                amount=amount,
                price=Decimal("0"),  # Market order
                dex_name=self.config.swap_provider,
                slippage_pct=float(self._slippage_pct),
                max_retries=self._max_retries,
            )
            self.lp_position_state.active_swap_order = TrackedOrder(order_id=order_id)
            self._swap_not_found_count = 0
            self.logger().info(f"Close-out swap order placed: {order_id}")

        except Exception as e:
            self.logger().error(f"Failed to place close-out swap: {e}")
            self._handle_swap_failure(e)

    # Close-out swap attempts before the executor stops fighting the market and
    # holds the withdrawn tokens instead (each attempt re-quotes at market).
    MAX_CLOSEOUT_SWAP_ATTEMPTS = 3

    def _handle_swap_failure(self, error: Exception):
        """Handle close-out swap failure.

        Bounded retries with a fresh quote each attempt; on exhaustion the
        executor terminates POSITION_HOLD carrying the withdrawn tokens instead of
        reporting FAILED with hidden exposure.
        """
        self.lp_position_state.active_swap_order = None
        self._swap_failure_count += 1
        # Widen for the next quote when the market moved further than the tolerance.
        self._widen_slippage(error)

        if self._swap_failure_count < self.MAX_CLOSEOUT_SWAP_ATTEMPTS:
            self.logger().error(
                f"Close-out swap failed (attempt {self._swap_failure_count}/"
                f"{self.MAX_CLOSEOUT_SWAP_ATTEMPTS}): {error}. Retrying with a fresh quote."
            )
            return  # stay in SWAPPING; next tick re-places at market

        self.logger().error(
            f"Close-out swap failed {self._swap_failure_count} times: {error}. "
            "Holding the withdrawn tokens instead of reporting FAILED with hidden exposure."
        )
        self._hold_reason = "closeout_swap_failed"
        self.close_type = CloseType.POSITION_HOLD
        current_price = self._current_price if self._current_price else Decimal("0")
        self._store_net_trade_from_withdrawal(current_price)
        self.lp_position_state.state = LPAmmExecutorStates.COMPLETE

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

    def _collect_held_position_orders(self) -> List[Dict]:
        """Snapshot a still-open position as a held order before the orchestrator reads it.

        force_stop_with_position_hold() (the orchestrator shutdown-deadline path)
        calls this directly, bypassing both the retry-exhaustion marker above and
        the normal close's _store_net_trade_from_withdrawal. Without this, a
        position still on-chain at a forced stop reports no held orders, so the
        orchestrator records FAILED instead of POSITION_HOLD and the live exposure
        falls out of tracking.
        """
        if self.lp_position_state.position_opened and not self._held_position_orders:
            self._hold_reason = self._hold_reason or "forced_stop"
            self._record_unclosed_position_marker()
        return super()._collect_held_position_orders()

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

        if net_base > 0 and net_quote > 0:
            # Both sides grew: fees earned on both at once, not a swap of one
            # token into the other. Folding this into a BUY/SELL would take
            # abs(net_quote) as a cost, inverting the quote gain into a loss.
            # Record it as earned value instead, via a negative fee (there is no
            # other field in this schema for "earned", only "paid").
            gained_quote = net_base * mid_price + net_quote
            self._held_position_orders.append({
                "client_order_id": order_id,
                "trading_pair": self.config.trading_pair,
                "trade_type": "BUY",  # dummy; executed amounts are 0, only the fee field carries value
                "price": float(mid_price),
                "executed_amount_base": 0.0,
                "executed_amount_quote": 0.0,
                "cumulative_fee_paid_quote": float(tx_fee_quote - gained_quote),
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
