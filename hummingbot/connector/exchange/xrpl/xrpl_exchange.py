import asyncio
import math
import time
import uuid
from decimal import ROUND_DOWN, Decimal
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union, cast

from bidict import bidict

# XRPL Imports
from xrpl.asyncio.clients import Client, XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException, sign
from xrpl.core.binarycodec import encode
from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    AccountObjects,
    AccountTx,
    AMMDeposit,
    AMMInfo,
    AMMWithdraw,
    Currency,
    IssuedCurrency,
    Memo,
    OfferCancel,
    Request,
    SubmitOnly,
    Transaction,
    Tx,
)
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.response import Response, ResponseStatus
from xrpl.utils import (
    drops_to_xrp,
    get_balance_changes,
    get_final_balances,
    get_order_book_changes,
    hex_to_str,
    ripple_time_to_posix,
    xrp_to_drops,
)
from xrpl.wallet import Wallet

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS, xrpl_web_utils
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_fill_processor import (
    extract_fill_amounts_from_balance_changes,
    extract_fill_amounts_from_offer_change,
    extract_fill_amounts_from_transaction,
    extract_transaction_data,
    find_offer_change_for_order,
)
from hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy import OrderPlacementStrategyFactory
from hummingbot.connector.exchange.xrpl.xrpl_utils import (  # AddLiquidityRequest,; GetPoolInfoRequest,; QuoteLiquidityRequest,; RemoveLiquidityRequest,
    AddLiquidityResponse,
    Ledger,
    PoolInfo,
    QuoteLiquidityResponse,
    RemoveLiquidityResponse,
    XRPLMarket,
    XRPLNodePool,
    autofill,
    convert_string_to_hex,
)
from hummingbot.connector.exchange.xrpl.xrpl_worker_manager import RequestPriority, XRPLWorkerPoolManager
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import (
    QueryResult,
    TransactionSubmitResult,
    TransactionVerifyResult,
    XRPLQueryWorkerPool,
    XRPLTransactionWorkerPool,
    XRPLVerificationWorkerPool,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule  # type: ignore
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class XRPLOrderTracker(ClientOrderTracker):
    TRADE_FILLS_WAIT_TIMEOUT = 20


class XrplExchange(ExchangePyBase):

    web_utils = xrpl_web_utils

    def __init__(
        self,
        xrpl_secret_key: str,
        wss_node_urls: list[str],
        max_request_per_minute: int,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        custom_markets: Optional[Dict[str, XRPLMarket]] = None,
    ):
        self._xrpl_secret_key = xrpl_secret_key

        # Create node pool with persistent connections for this connector instance
        self._node_pool = XRPLNodePool(
            node_urls=wss_node_urls,
            requests_per_10s=2 if isinstance(max_request_per_minute, str) else max_request_per_minute / 6,
            burst_tokens=5,  # Reserved for transaction submissions only
            max_burst_tokens=10,  # Keep low - burst only for tx submissions/cancels
            health_check_interval=CONSTANTS.CONNECTION_POOL_HEALTH_CHECK_INTERVAL,
            connection_timeout=CONSTANTS.CONNECTION_POOL_TIMEOUT,
            max_connection_age=CONSTANTS.CONNECTION_POOL_MAX_AGE,
        )

        # Create worker pool manager for this connector instance
        self._worker_manager = XRPLWorkerPoolManager(
            node_pool=self._node_pool,
            query_pool_size=CONSTANTS.QUERY_WORKER_POOL_SIZE if trading_required else 1,
            verification_pool_size=CONSTANTS.VERIFICATION_WORKER_POOL_SIZE if trading_required else 1,
            transaction_pool_size=CONSTANTS.TX_WORKER_POOL_SIZE if trading_required else 1,
        )

        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._xrpl_auth: XRPLAuth = self.authenticator
        self._trading_pair_symbol_map: Optional[Mapping[str, str]] = None
        self._trading_pair_fee_rules: Dict[str, Dict[str, Any]] = {}

        self._nonce_creator = NonceCreator.for_milliseconds()
        self._custom_markets = custom_markets or {}
        self._last_clients_refresh_time = 0

        # Order state locking to prevent concurrent status updates
        self._order_status_locks: Dict[str, asyncio.Lock] = {}
        self._order_status_lock_manager_lock = asyncio.Lock()

        # Worker pools (lazy initialization after start_network)
        self._tx_pool: Optional[XRPLTransactionWorkerPool] = None
        self._query_pool: Optional[XRPLQueryWorkerPool] = None
        self._verification_pool: Optional[XRPLVerificationWorkerPool] = None

        self._first_run = True

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    def _create_order_tracker(self) -> ClientOrderTracker:
        return XRPLOrderTracker(connector=self)

    @staticmethod
    def xrpl_order_type(order_type: OrderType) -> int:
        return CONSTANTS.XRPL_ORDER_TYPE[order_type]

    @staticmethod
    def to_hb_order_type(order_type: str) -> OrderType:
        return OrderType[order_type]

    @property
    def authenticator(self) -> XRPLAuth:
        return XRPLAuth(xrpl_secret_key=self._xrpl_secret_key)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return "Not Supported"

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return ""

    @property
    def trading_pairs_request_path(self):
        return ""

    @property
    def check_network_request_path(self):
        return ""

    @property
    def trading_pairs(self):
        return self._trading_pairs or []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def _get_async_client(self):
        client = await self._node_pool.get_client(True)
        return client

    # @property
    # def user_stream_client(self) -> AsyncWebsocketClient:
    #     # For user stream, always get a fresh client from the pool
    #     # This must be used in async context, so we return a coroutine
    #     raise NotImplementedError("Use await self._get_async_client() instead of user_stream_client property.")

    # @property
    # def order_book_data_client(self) -> AsyncWebsocketClient:
    #     # For order book, always get a fresh client from the pool
    #     # This must be used in async context, so we return a coroutine
    #     raise NotImplementedError("Use await self._get_async_client() instead of order_book_data_client property.")

    @property
    def auth(self) -> XRPLAuth:
        return self._xrpl_auth

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET, OrderType.AMM_SWAP]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # We do not use time synchronizer in XRPL connector
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: this will be important to implement in case that we request an order that is in memory but the update of it wasn't correct
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: this will be important to implement in case that we request an order that is in memory but the update of it wasn't correct
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:  # type: ignore
        pass

    def _create_order_book_data_source(self) -> XRPLAPIOrderBookDataSource:
        return XRPLAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs or [],
            connector=self,
            api_factory=self._web_assistants_factory,
            worker_manager=self._worker_manager,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        polling_source = XRPLAPIUserStreamDataSource(
            auth=self._xrpl_auth,
            connector=self,
            worker_manager=self._worker_manager,
        )

        return polling_source

    async def _ensure_network_started(self):
        """
        Ensure that the network components (node pool and worker manager) are started.

        This is called automatically when _query_xrpl is invoked before start_network,
        such as during initial connection validation via UserBalances.add_exchange.
        It only starts the essential components needed for queries, not the full
        network stack (order book tracker, user stream, etc.).
        """
        if not self._node_pool.is_running:
            self.logger().debug("Auto-starting node pool for early query...")
            await self._node_pool.start()

        if not self._worker_manager.is_running:
            self.logger().debug("Auto-starting worker manager for early query...")
            await self._worker_manager.start()

    async def start_network(self):
        """
        Start all required tasks for the XRPL connector.

        This includes:
        - Starting the base network tasks (order book tracker, polling loops, etc.)
        - Starting the persistent connection pool
        - Starting the worker pool manager
        - Registering request handlers

        Note: We call super().start_network() FIRST because the parent class
        calls stop_network() at the beginning to ensure a clean state. If we
        start our resources before calling super(), they would be immediately
        stopped and then we'd need to restart them.
        """
        self.logger().info("Starting XRPL connector network...")
        # Now start XRPL-specific resources (after parent's stop_network call)
        # Start the persistent connection pool
        await self._node_pool.start()

        # Wait for at least one healthy connection before proceeding
        # This prevents race conditions where polling loops start before connections are ready
        max_wait_seconds = 30
        wait_interval = 1.0
        elapsed = 0.0
        while self._node_pool.healthy_connection_count == 0 and elapsed < max_wait_seconds:
            self.logger().debug(
                f"Waiting for healthy XRPL connections... ({elapsed:.0f}s/{max_wait_seconds}s)"
            )
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval

        if self._node_pool.healthy_connection_count == 0:
            self.logger().error(
                f"No healthy XRPL connections established after {max_wait_seconds}s timeout. "
                "Network operations may fail until connections are restored."
            )
        else:
            self.logger().debug(
                f"Node pool ready with {self._node_pool.healthy_connection_count} healthy connections"
            )

        # Start the worker pool manager
        await self._worker_manager.start()
        self.logger().debug("Worker pool manager started")

        # Initialize specialized workers
        self._init_specialized_workers()

        self.logger().debug("XRPL connector network started successfully")

        await cast(XRPLAPIUserStreamDataSource, self._user_stream_tracker._data_source)._initialize_ledger_index()

        await super().start_network()

    async def stop_network(self):
        """
        Stop all network-related tasks for the XRPL connector.

        This includes:
        - Stopping the base network tasks
        - Stopping the worker pool manager (if running)
        - Stopping the persistent connection pool (if running)

        Note: This method is called by super().start_network() to ensure clean state,
        so we guard against stopping resources that haven't been started yet.
        """
        if not self._first_run:
            self.logger().info("Stopping XRPL connector network...")

            # Stop the worker pool manager (only if it's running)
            if self._worker_manager.is_running:
                await self._worker_manager.stop()
                self.logger().debug("Worker pool manager stopped")

            # Stop the persistent connection pool (only if it's running)
            if self._node_pool.is_running:
                await self._node_pool.stop()
                self.logger().debug("Node pool stopped")

            self.logger().info("XRPL connector network stopped successfully")

        self._first_run = False

        # Call parent stop_network first
        await super().stop_network()

    def _init_specialized_workers(self):
        """Initialize worker pools for the connector."""
        # Query pool for read-only operations
        self._query_pool = self._worker_manager.get_query_pool()

        # Verification pool for transaction finality checks
        self._verification_pool = self._worker_manager.get_verification_pool()

        # Transaction pool for order placement/cancellation
        # This requires the wallet for signing
        self._tx_pool = self._worker_manager.get_transaction_pool(
            wallet=self._xrpl_auth.get_wallet(),
            pool_id=self._xrpl_auth.get_account(),
        )

        self.logger().debug("Worker pools initialized")

    @property
    def tx_pool(self) -> XRPLTransactionWorkerPool:
        """Get the transaction worker pool, initializing if needed."""
        if self._tx_pool is None:
            self._tx_pool = self._worker_manager.get_transaction_pool(
                wallet=self._xrpl_auth.get_wallet(),
                pool_id=self._xrpl_auth.get_account(),
            )
        return self._tx_pool

    @property
    def query_pool(self) -> XRPLQueryWorkerPool:
        """Get the query worker pool, initializing if needed."""
        if self._query_pool is None:
            self._query_pool = self._worker_manager.get_query_pool()
        return self._query_pool

    @property
    def verification_pool(self) -> XRPLVerificationWorkerPool:
        """Get the verification worker pool, initializing if needed."""
        if self._verification_pool is None:
            self._verification_pool = self._worker_manager.get_verification_pool()
        return self._verification_pool

    async def _query_xrpl(
        self,
        request: Request,
        priority: int = RequestPriority.MEDIUM,
        timeout: Optional[float] = None,
    ) -> Response:
        """
        Execute an XRPL query using the query worker pool.

        This is the preferred method for executing XRPL queries. It uses the
        XRPLQueryWorkerPool for connection management, concurrency, and rate limiting.

        Args:
            request: The XRPL request to execute
            priority: Request priority (unused, kept for API compatibility)
            timeout: Optional timeout override

        Returns:
            The full Response object from XRPL
        """
        # Ensure worker pool is started before submitting requests
        # This handles the case where _update_balances is called before start_network
        # (e.g., during initial connection validation via UserBalances.add_exchange)
        if not self._worker_manager.is_running:
            await self._ensure_network_started()

        # Use query pool - submit method handles concurrent execution
        result: QueryResult = await self.query_pool.submit(request, timeout=timeout)

        if not result.success:
            # If query failed, raise an exception or return error response
            self.logger().warning(f"Query failed: {result.error}")
            # Return the response if available, otherwise raise
            if result.response is not None:
                return result.response
            raise Exception(f"Query failed: {result.error}")

        # result.response is guaranteed to be non-None when success=True
        assert result.response is not None
        return result.response

    async def _submit_transaction(
        self,
        transaction: Transaction,
        priority: int = RequestPriority.HIGH,
        fail_hard: bool = True,
    ) -> Dict[str, Any]:
        """
        Submit a transaction using the transaction worker pool.

        This method handles autofill, signing, and submission in one call.
        Used primarily for deposit/withdraw operations (AMM liquidity).

        Args:
            transaction: The unsigned transaction to submit
            priority: Request priority (unused, kept for API compatibility)
            fail_hard: Whether to use fail_hard mode

        Returns:
            Dict containing signed_tx, response, prelim_result, exchange_order_id
        """
        # Use tx_pool for concurrent preparation, serialized submission
        submit_result: TransactionSubmitResult = await self.tx_pool.submit_transaction(
            transaction=transaction,
            fail_hard=fail_hard,
            max_retries=3,  # Default retries for deposit/withdraw
        )

        # Convert TransactionSubmitResult to dict for backward compatibility
        return {
            "signed_tx": submit_result.signed_tx,
            "response": submit_result.response,
            "prelim_result": submit_result.prelim_result,
            "exchange_order_id": submit_result.exchange_order_id,
        }

    async def _get_order_status_lock(self, client_order_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific order to prevent concurrent status updates.

        :param client_order_id: The client order ID to get a lock for
        :return: An asyncio.Lock for the specified order
        """
        async with self._order_status_lock_manager_lock:
            if client_order_id not in self._order_status_locks:
                self._order_status_locks[client_order_id] = asyncio.Lock()
            return self._order_status_locks[client_order_id]

    async def _cleanup_order_status_lock(self, client_order_id: str):
        """
        Clean up the lock for a specific order after it's no longer needed.

        :param client_order_id: The client order ID to clean up the lock for
        """
        async with self._order_status_lock_manager_lock:
            if client_order_id in self._order_status_locks:
                del self._order_status_locks[client_order_id]

    async def _process_final_order_state(
        self,
        tracked_order: InFlightOrder,
        new_state: OrderState,
        update_timestamp: float,
        trade_update: Optional[TradeUpdate] = None,
    ):
        """
        Process order reaching a final state (FILLED, CANCELED, FAILED).
        This ensures proper order completion flow and cleanup.

        :param tracked_order: The order that reached a final state
        :param new_state: The final state (FILLED, CANCELED, or FAILED)
        :param update_timestamp: Timestamp of the state change
        :param trade_update: Optional trade update to process
        """
        # For FILLED orders, fetch ALL trade updates from ledger history to ensure no fills are missed.
        # This is a safety net for cases where:
        # 1. Taker fills at order creation arrived before the order was tracked
        # 2. Rapid consecutive fills were processed out of order
        # 3. Any other edge cases that could cause missed fills
        # The InFlightOrder.update_with_trade_update() method handles deduplication via trade_id.
        if new_state == OrderState.FILLED:
            try:
                all_trade_updates = await self._all_trade_updates_for_order(tracked_order)
                fills_before = len(tracked_order.order_fills)

                for tu in all_trade_updates:
                    self._order_tracker.process_trade_update(tu)

                fills_after = len(tracked_order.order_fills)
                if fills_after > fills_before:
                    self.logger().debug(
                        f"[FILL_RECOVERY] Order {tracked_order.client_order_id}: recovered {fills_after - fills_before} "
                        f"missed fill(s) from ledger history (total fills: {fills_after})"
                    )

                # Log final fill summary
                self.logger().debug(
                    f"[ORDER_COMPLETE] Order {tracked_order.client_order_id} FILLED: "
                    f"executed={tracked_order.executed_amount_base}/{tracked_order.amount}, "
                    f"fills={len(tracked_order.order_fills)}"
                )
            except Exception as e:
                self.logger().warning(
                    f"[FILL_RECOVERY] Failed to fetch all trade updates for order {tracked_order.client_order_id}: {e}. "
                    f"Proceeding with available fill data."
                )
                # Still process the trade_update if provided, as fallback
                if trade_update:
                    self._order_tracker.process_trade_update(trade_update)
        elif trade_update:
            # For non-FILLED final states, just process the provided trade update
            self._order_tracker.process_trade_update(trade_update)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
        )

        # Process the order update (this will call _trigger_order_completion -> stop_tracking_order)
        # For FILLED orders, this will wait for completely_filled_event before proceeding
        self._order_tracker.process_order_update(order_update)

        # XRPL-specific cleanup
        await self._cleanup_order_status_lock(tracked_order.client_order_id)

        self.logger().debug(f"[ORDER] Order {tracked_order.client_order_id} reached final state: {new_state.name}")

    async def _process_market_order_transaction(
        self, tracked_order: InFlightOrder, transaction: Dict, meta: Dict, event_message: Dict
    ):
        """
        Process market order transaction from user stream events.

        :param tracked_order: The tracked order to process
        :param transaction: Transaction data from the event
        :param meta: Transaction metadata
        :param event_message: Complete event message
        """
        # Use order lock to prevent race conditions with cancellation
        order_lock = await self._get_order_status_lock(tracked_order.client_order_id)
        async with order_lock:
            # Double-check state after acquiring lock to prevent race conditions
            if tracked_order.current_state not in [OrderState.OPEN]:
                self.logger().debug(
                    f"Order {tracked_order.client_order_id} state changed to {tracked_order.current_state} while acquiring lock, skipping update"
                )
                return

            tx_status = meta.get("TransactionResult")
            if tx_status != "tesSUCCESS":
                self.logger().error(
                    f"Order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}) failed: {tx_status}, data: {event_message}"
                )
                new_order_state = OrderState.FAILED
            else:
                new_order_state = OrderState.FILLED

            # Enhanced logging for debugging race conditions
            self.logger().debug(
                f"[USER_STREAM_MARKET] Order {tracked_order.client_order_id} state transition: "
                f"{tracked_order.current_state.name} -> {new_order_state.name} "
                f"(tx_status: {tx_status})"
            )

            update_timestamp = time.time()
            trade_update = None

            if new_order_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                trade_update = await self.process_trade_fills(event_message, tracked_order)
                if trade_update is None:
                    self.logger().error(
                        f"Failed to process trade fills for order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}), order state: {new_order_state}, data: {event_message}"
                    )

            # Process final state using centralized method (handles stop_tracking_order)
            if new_order_state in [OrderState.FILLED, OrderState.FAILED]:
                await self._process_final_order_state(tracked_order, new_order_state, update_timestamp, trade_update)
            else:
                # For non-final states, only process update if state actually changed
                if tracked_order.current_state != new_order_state:
                    order_update = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=tracked_order.exchange_order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=update_timestamp,
                        new_state=new_order_state,
                    )
                    self._order_tracker.process_order_update(order_update=order_update)
                if trade_update:
                    self._order_tracker.process_trade_update(trade_update)

    async def _process_order_book_changes(self, order_book_changes: List[Any], transaction: Dict, event_message: Dict):
        """
        Process order book changes from user stream events.

        :param order_book_changes: List of order book changes
        :param transaction: Transaction data from the event
        :param event_message: Complete event message
        """
        # Debug logging: Log incoming event details
        tx_hash = transaction.get("hash", "")
        tx_seq = transaction.get("Sequence")
        self.logger().debug(
            f"[ORDER_BOOK_CHANGES_DEBUG] Processing: {tx_hash}, seq={tx_seq}, "
            f"changes={len(order_book_changes)}"
        )

        # Handle state updates for orders
        for order_book_change in order_book_changes:
            if order_book_change["maker_account"] != self._xrpl_auth.get_account():
                self.logger().debug(f"Order book change not for this account? {order_book_change['maker_account']}")
                continue

            # Debug: Log all offer changes for our account
            self.logger().debug(
                f"[ORDER_BOOK_CHANGES_DEBUG] Our account offer_changes count: "
                f"{len(order_book_change.get('offer_changes', []))}"
            )

            for offer_change in order_book_change["offer_changes"]:
                offer_seq = offer_change.get("sequence")
                offer_status = offer_change.get("status")
                self.logger().debug(
                    f"[ORDER_BOOK_CHANGES_DEBUG] Offer change: seq={offer_seq}, status={offer_status}, "
                    f"taker_gets={offer_change.get('taker_gets')}, taker_pays={offer_change.get('taker_pays')}"
                )

                tracked_order = self.get_order_by_sequence(offer_change["sequence"])
                if tracked_order is None:
                    self.logger().debug(f"Tracked order not found for sequence '{offer_change['sequence']}'")
                    continue

                self.logger().debug(
                    f"[ORDER_BOOK_CHANGES_DEBUG] Found tracked order: {tracked_order.client_order_id}, "
                    f"current_state={tracked_order.current_state.name}, "
                    f"executed_amount={tracked_order.executed_amount_base}/{tracked_order.amount}"
                )

                if tracked_order.current_state in [OrderState.PENDING_CREATE]:
                    self.logger().debug(
                        f"[ORDER_BOOK_CHANGES_DEBUG] Skipping order {tracked_order.client_order_id} - PENDING_CREATE"
                    )
                    continue

                # Use order lock to prevent race conditions
                order_lock = await self._get_order_status_lock(tracked_order.client_order_id)
                async with order_lock:
                    # Double-check state after acquiring lock to prevent race conditions
                    tracked_order = self.get_order_by_sequence(offer_change["sequence"])

                    if tracked_order is None:
                        continue

                    # Check if order is in a final state to avoid duplicate updates
                    if tracked_order.current_state in [
                        OrderState.FILLED,
                        OrderState.CANCELED,
                        OrderState.FAILED,
                    ]:
                        self.logger().debug(
                            f"Order {tracked_order.client_order_id} already in final state {tracked_order.current_state}, skipping update"
                        )
                        continue

                    status = offer_change["status"]
                    if status == "filled":
                        new_order_state = OrderState.FILLED

                    elif status == "partially-filled":
                        new_order_state = OrderState.PARTIALLY_FILLED
                    elif status == "cancelled":
                        new_order_state = OrderState.CANCELED
                    else:
                        # Check if the transaction did cross any offers in the order book
                        taker_gets = offer_change.get("taker_gets")
                        taker_pays = offer_change.get("taker_pays")

                        tx_taker_gets = transaction.get("TakerGets")
                        tx_taker_pays = transaction.get("TakerPays")

                        if isinstance(tx_taker_gets, str):
                            tx_taker_gets = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_gets))}

                        if isinstance(tx_taker_pays, str):
                            tx_taker_pays = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_pays))}

                        # Use a small tolerance for comparing decimal values
                        tolerance = Decimal("0.00001")  # 0.001% tolerance

                        taker_gets_value = Decimal(taker_gets.get("value", "0") if taker_gets else "0")
                        tx_taker_gets_value = Decimal(tx_taker_gets.get("value", "0") if tx_taker_gets else "0")
                        taker_pays_value = Decimal(taker_pays.get("value", "0") if taker_pays else "0")
                        tx_taker_pays_value = Decimal(tx_taker_pays.get("value", "0") if tx_taker_pays else "0")

                        # Check if values differ by more than the tolerance
                        gets_diff = abs(
                            (taker_gets_value - tx_taker_gets_value) / tx_taker_gets_value if tx_taker_gets_value else 0
                        )
                        pays_diff = abs(
                            (taker_pays_value - tx_taker_pays_value) / tx_taker_pays_value if tx_taker_pays_value else 0
                        )

                        if gets_diff > tolerance or pays_diff > tolerance:
                            new_order_state = OrderState.PARTIALLY_FILLED
                        else:
                            new_order_state = OrderState.OPEN

                    # INFO level logging for significant state changes
                    if new_order_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED, OrderState.CANCELED]:
                        self.logger().debug(
                            f"[ORDER] Order {tracked_order.client_order_id} state: "
                            f"{tracked_order.current_state.name} -> {new_order_state.name} "
                            f"(offer_status: {status})"
                        )
                    else:
                        self.logger().debug(
                            f"Order update for order '{tracked_order.client_order_id}' with sequence '{offer_change['sequence']}': '{new_order_state}'"
                        )
                    # Enhanced logging for debugging race conditions
                    self.logger().debug(
                        f"[USER_STREAM] Order {tracked_order.client_order_id} state transition: "
                        f"{tracked_order.current_state.name} -> {new_order_state.name} "
                        f"(sequence: {offer_change['sequence']}, status: {status})"
                    )

                    update_timestamp = time.time()
                    trade_update = None

                    if new_order_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                        trade_update = await self.process_trade_fills(event_message, tracked_order)
                        if trade_update is None:
                            self.logger().error(
                                f"Failed to process trade fills for order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}), order state: {new_order_state}, data: {event_message}"
                            )

                    # Process final state using centralized method (handles stop_tracking_order)
                    if new_order_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
                        await self._process_final_order_state(
                            tracked_order, new_order_state, update_timestamp, trade_update
                        )
                    else:
                        # For non-final states, only process update if state actually changed
                        if tracked_order.current_state != new_order_state:
                            order_update = OrderUpdate(
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=tracked_order.exchange_order_id,
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=update_timestamp,
                                new_state=new_order_state,
                            )
                            self._order_tracker.process_order_update(order_update=order_update)
                        if trade_update:
                            self._order_tracker.process_trade_update(trade_update)

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> AddedToCostTradeFee:
        # TODO: Implement get fee, use the below implementation
        # is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        # trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        # if trading_pair in self._trading_fees:
        #     fees_data = self._trading_fees[trading_pair]
        #     fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
        #     fee = AddedToCostTradeFee(percent=fee_value)

        # TODO: Remove this fee implementation
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(  # type: ignore
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> tuple[str, float, Response | None]:
        """
        Places an order using the specialized transaction worker.

        The transaction worker handles:
        - Serialized submission through pipeline (prevents sequence conflicts)
        - Sequence error retries with exponential backoff
        - Autofill, sign, and submit in one atomic operation

        Returns a tuple of (exchange_order_id, transaction_time, response).
        """
        o_id = "UNKNOWN"
        transact_time = 0.0
        resp = None

        self.logger().debug(
            f"[PLACE_ORDER] Starting: order_id={order_id}, pair={trading_pair}, "
            f"amount={amount}, price={price}, type={order_type}"
        )

        try:
            # Create order object for strategy
            order = InFlightOrder(
                client_order_id=order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self._time(),
            )

            # Create the transaction using the appropriate strategy
            strategy = OrderPlacementStrategyFactory.create_strategy(self, order)
            transaction = await strategy.create_order_transaction()

            self.logger().debug(f"[PLACE_ORDER] Created transaction for order_id={order_id}")

            # Submit through the transaction worker pool
            # This handles: concurrent prep, pipeline serialization, autofill, sign, submit, sequence error retries
            submit_result: TransactionSubmitResult = await self.tx_pool.submit_transaction(
                transaction=transaction,
                fail_hard=True,
                max_retries=CONSTANTS.PLACE_ORDER_MAX_RETRY,
            )

            transact_time = time.time()

            # Update order state to PENDING_CREATE
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=transact_time,
                new_state=OrderState.PENDING_CREATE,
            )
            self._order_tracker.process_order_update(order_update)

            # Check submission result
            if not submit_result.success:
                self.logger().error(
                    f"[PLACE_ORDER] Order {order_id} submission failed: {submit_result.error}"
                )
                raise Exception(f"Order submission failed: {submit_result.error}")

            o_id = submit_result.exchange_order_id or "UNKNOWN"
            signed_tx = submit_result.signed_tx
            prelim_result = submit_result.prelim_result

            self.logger().debug(
                f"[PLACE_ORDER] Submitted order {order_id} ({o_id}): "
                f"prelim_result={prelim_result}, tx_hash={submit_result.tx_hash}"
            )

            # Verify the transaction landed on the ledger
            if submit_result.is_accepted and signed_tx is not None:
                verify_result: TransactionVerifyResult = await self.verification_pool.submit_verification(
                    signed_tx=signed_tx,
                    prelim_result=prelim_result or "tesSUCCESS",
                    timeout=CONSTANTS.VERIFY_TX_TIMEOUT,
                )

                if verify_result.verified:
                    self.logger().debug(f"[PLACE_ORDER] Order {order_id} ({o_id}) verified on ledger")
                    resp = verify_result.response
                    # NOTE: Do NOT update order state here - let _place_order_and_process_update() handle it
                    # via _request_order_status() to avoid duplicate order creation events
                else:
                    # Verification failed - log but don't update state here
                    # Let _place_order_and_process_update() handle the failure
                    self.logger().error(
                        f"[PLACE_ORDER] Order {order_id} ({o_id}) verification failed: {verify_result.error}"
                    )
                    raise Exception(f"Order verification failed: {verify_result.error}")
            else:
                # Transaction was not accepted
                self.logger().error(
                    f"[PLACE_ORDER] Order {order_id} not accepted: prelim_result={prelim_result}"
                )
                raise Exception(f"Order not accepted: {prelim_result}")

        except Exception as e:
            # NOTE: Do NOT update order state here - let _place_order_and_process_update() handle it
            # This prevents duplicate order creation/failed events
            self.logger().error(
                f"[PLACE_ORDER] Order {o_id} ({order_id}) failed: {str(e)}, "
                f"type={order_type}, pair={trading_pair}, amount={amount}, price={price}"
            )
            raise Exception(f"Order {o_id} ({order_id}) creation failed: {e}")

        return o_id, transact_time, resp

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        """
        Place an order and process the order update.

        This is the SINGLE source of truth for order state transitions after PENDING_CREATE.
        The _place_order() method only submits and verifies the transaction, but does not
        update order state (except for the initial PENDING_CREATE).
        """
        exchange_order_id = None
        try:
            # No lock needed - worker pool handles concurrency
            exchange_order_id, update_timestamp, order_creation_resp = await self._place_order(
                order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                amount=order.amount,
                trade_type=order.trade_type,
                order_type=order.order_type,
                price=order.price,
                **kwargs,
            )

            # Set exchange_order_id on the order object so _request_order_status() can use it
            order.update_exchange_order_id(exchange_order_id)

            # Log order creation
            self.logger().debug(
                f"[ORDER] Order {order.client_order_id} created: {order.order_type.name} {order.trade_type.name} "
                f"{order.amount} {order.trading_pair} @ {order.price if order.order_type == OrderType.LIMIT else 'MARKET'}"
            )

            order_update = await self._request_order_status(
                order,
                creation_tx_resp=order_creation_resp.to_dict().get("result") if order_creation_resp is not None else None,
            )

            # Log the initial order state after creation
            self.logger().debug(
                f"[ORDER] Order {order.client_order_id} initial state: {order_update.new_state.name}"
            )

            # Handle order state based on whether it's a final state or not
            if order_update.new_state == OrderState.FILLED:
                # For FILLED orders, use centralized final state processing which:
                # 1. Fetches ALL trade updates from ledger history (safety net for missed fills)
                # 2. Processes them with deduplication
                # 3. Logs [ORDER_COMPLETE] summary
                # 4. Calls process_order_update() to trigger completion events
                # 5. Performs cleanup
                await self._process_final_order_state(
                    order, OrderState.FILLED, order_update.update_timestamp
                )
            elif order_update.new_state == OrderState.PARTIALLY_FILLED:
                # For PARTIALLY_FILLED orders, process the order update and initial fills
                # The order remains active and will receive more fills via user stream
                self._order_tracker.process_order_update(order_update)
                trade_update = await self.process_trade_fills(
                    order_creation_resp.to_dict() if order_creation_resp is not None else None, order
                )
                if trade_update is not None:
                    self._order_tracker.process_trade_update(trade_update)
                else:
                    self.logger().error(
                        f"Failed to process trade fills for order {order.client_order_id} ({order.exchange_order_id}), "
                        f"order state: {order_update.new_state}, data: {order_creation_resp.to_dict() if order_creation_resp is not None else 'None'}"
                    )
            else:
                # For non-fill states (OPEN, PENDING_CREATE, etc.), just process the order update
                self._order_tracker.process_order_update(order_update)

            return exchange_order_id

        except Exception as e:
            # Handle order creation failure - this is the ONLY place we set FAILED state
            self.logger().error(
                f"[ORDER] Order {order.client_order_id} creation failed: {str(e)}"
            )
            order_update = OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=time.time(),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            raise

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> TransactionSubmitResult:
        """
        Place a cancel order using the specialized transaction worker.

        The transaction worker handles:
        - Serialized submission through pipeline (prevents sequence conflicts)
        - Sequence error retries with exponential backoff
        - Autofill, sign, and submit in one atomic operation

        Args:
            order_id: The client order ID
            tracked_order: The tracked order to cancel

        Returns:
            TransactionSubmitResult with the submission outcome
        """
        exchange_order_id = tracked_order.exchange_order_id

        if exchange_order_id is None:
            self.logger().error(f"Unable to cancel order {order_id}, it does not yet have exchange order id")
            return TransactionSubmitResult(
                success=False,
                error="No exchange order ID",
            )

        try:
            offer_sequence, _, _ = exchange_order_id.split("-")
            memo = Memo(
                memo_data=convert_string_to_hex(order_id, padding=False),
            )
            transaction = OfferCancel(
                account=self._xrpl_auth.get_account(),
                offer_sequence=int(offer_sequence),
                memos=[memo],
            )

            self.logger().debug(
                f"[PLACE_CANCEL] Starting: order_id={order_id}, exchange_order_id={exchange_order_id}, "
                f"offer_sequence={offer_sequence}"
            )

            # Submit through the transaction worker pool
            # This handles: concurrent prep, pipeline serialization, autofill, sign, submit, sequence error retries
            submit_result: TransactionSubmitResult = await self.tx_pool.submit_transaction(
                transaction=transaction,
                fail_hard=True,
                max_retries=CONSTANTS.CANCEL_MAX_RETRY,
            )

            self.logger().debug(
                f"[PLACE_CANCEL] Submitted cancel for order {order_id} ({exchange_order_id}): "
                f"success={submit_result.success}, prelim_result={submit_result.prelim_result}, "
                f"tx_hash={submit_result.tx_hash}"
            )

            # Handle temBAD_SEQUENCE specially - means offer was already cancelled or filled
            # This is a "success" in the sense that the offer is gone
            if submit_result.prelim_result == "temBAD_SEQUENCE":
                self.logger().debug(
                    f"[PLACE_CANCEL] Order {order_id} got temBAD_SEQUENCE - "
                    f"offer was likely already cancelled or filled"
                )
                return TransactionSubmitResult(
                    success=True,
                    signed_tx=submit_result.signed_tx,
                    response=submit_result.response,
                    prelim_result=submit_result.prelim_result,
                    exchange_order_id=submit_result.exchange_order_id,
                    tx_hash=submit_result.tx_hash,
                    error=None,
                )

            return submit_result

        except Exception as e:
            self.logger().error(f"Order cancellation failed: {e}, order_id: {exchange_order_id}")
            return TransactionSubmitResult(
                success=False,
                error=str(e),
            )

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        """
        Execute order cancellation using the worker pools.

        Uses order-specific locks to prevent concurrent cancel attempts on the same order.
        The tx_pool handles transaction submission and the verification_pool handles finality.
        """
        # Use order-specific lock to prevent concurrent cancel attempts on the same order
        order_lock = await self._get_order_status_lock(order.client_order_id)

        async with order_lock:
            if not self.ready:
                await self._sleep(3)

            # Early exit if order is not being tracked and is already in a final state
            is_actively_tracked = order.client_order_id in self._order_tracker.active_orders
            if not is_actively_tracked and order.current_state in [
                OrderState.FILLED,
                OrderState.CANCELED,
                OrderState.FAILED,
            ]:
                self.logger().debug(
                    f"[CANCEL] Order {order.client_order_id} no longer tracked after lock, final state {order.current_state}, "
                    f"processing final state to remove from lost orders"
                )
                # Process an OrderUpdate with the final state to trigger cleanup in the order tracker
                update_timestamp = self.current_timestamp
                if update_timestamp is None or math.isnan(update_timestamp):
                    update_timestamp = self._time()
                order_update = OrderUpdate(
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    update_timestamp=update_timestamp,
                    new_state=order.current_state,
                )
                self._order_tracker.process_order_update(order_update)
                return order.current_state == OrderState.CANCELED

            # Check current order state before attempting cancellation
            current_state = order.current_state
            if current_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
                self.logger().debug(
                    f"[CANCEL] Order {order.client_order_id} already in final state {current_state}, skipping cancellation"
                )
                return current_state == OrderState.CANCELED

            self.logger().debug(
                f"[CANCEL] Order {order.client_order_id} starting cancellation process, current_state={current_state}"
            )

            # Wait for exchange_order_id if order is still pending creation
            # This handles the edge case where cancellation is triggered (e.g., during bot shutdown)
            # before the order placement has completed and received its exchange_order_id
            if order.exchange_order_id is None:
                self.logger().debug(
                    f"[CANCEL] Order {order.client_order_id} is in {current_state.name} without exchange_order_id, "
                    f"waiting for order creation to complete..."
                )
                try:
                    await order.get_exchange_order_id()  # Has 10-second timeout built-in
                    self.logger().debug(
                        f"[CANCEL] Order {order.client_order_id} now has exchange_order_id: {order.exchange_order_id}"
                    )
                except asyncio.TimeoutError:
                    self.logger().warning(
                        f"[CANCEL] Timeout waiting for exchange_order_id for order {order.client_order_id}. "
                        f"Order may not have been submitted to the exchange."
                    )
                    # Mark the order as failed since we couldn't get confirmation
                    await self._order_tracker.process_order_not_found(order.client_order_id)
                    await self._cleanup_order_status_lock(order.client_order_id)
                    return False

            update_timestamp = self.current_timestamp
            if update_timestamp is None or math.isnan(update_timestamp):
                update_timestamp = self._time()

            # Mark order as pending cancellation
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=OrderState.PENDING_CANCEL,
            )
            self._order_tracker.process_order_update(order_update)

            # Get fresh order status before attempting cancellation
            try:
                fresh_order_update = await self._request_order_status(order)

                self.logger().debug(
                    f"[CANCEL] Order {order.client_order_id} fresh status check: {fresh_order_update.new_state.name}"
                )

                # If order is FULLY filled, process the fills and don't cancel (nothing to cancel)
                if fresh_order_update.new_state == OrderState.FILLED:
                    self.logger().debug(
                        f"[CANCEL] Order {order.client_order_id} is FILLED, processing fills instead of canceling"
                    )

                    trade_updates = await self._all_trade_updates_for_order(order)
                    first_trade_update = trade_updates[0] if len(trade_updates) > 0 else None

                    # Use centralized final state processing for filled orders
                    await self._process_final_order_state(
                        order, OrderState.FILLED, fresh_order_update.update_timestamp, first_trade_update
                    )
                    # Process any remaining trade updates
                    for trade_update in trade_updates[1:]:
                        self._order_tracker.process_trade_update(trade_update)

                    return False  # Cancellation not needed - order is fully filled

                # If order is already canceled, return success
                elif fresh_order_update.new_state == OrderState.CANCELED:
                    self.logger().debug(f"[CANCEL] Order {order.client_order_id} already canceled on ledger")
                    # Use centralized final state processing for already cancelled orders
                    await self._process_final_order_state(
                        order, OrderState.CANCELED, fresh_order_update.update_timestamp
                    )
                    return True

                # For PARTIALLY_FILLED orders, process fills first then CONTINUE with cancellation
                # This is important: we need to cancel the remaining unfilled portion
                elif fresh_order_update.new_state == OrderState.PARTIALLY_FILLED:
                    self.logger().debug(
                        f"[CANCEL] Order {order.client_order_id} is PARTIALLY_FILLED, "
                        f"processing fills then proceeding with cancellation of remaining amount"
                    )

                    trade_updates = await self._all_trade_updates_for_order(order)
                    # Process fills but DON'T return - continue to cancel the remaining portion
                    self._order_tracker.process_order_update(fresh_order_update)
                    for trade_update in trade_updates:
                        self._order_tracker.process_trade_update(trade_update)
                    # Fall through to cancellation code below

            except Exception as status_check_error:
                self.logger().warning(
                    f"[CANCEL] Failed to check order status before cancellation for {order.client_order_id}: {status_check_error}"
                )

            # Proceed with cancellation attempt using worker pools
            # _place_cancel uses tx_pool which handles sequence error retries internally
            submit_result: TransactionSubmitResult = await self._place_cancel(order.client_order_id, order)

            if not submit_result.success:
                self.logger().error(
                    f"[CANCEL] Order {order.client_order_id} submission failed: {submit_result.error}"
                )
                await self._order_tracker.process_order_not_found(order.client_order_id)
                await self._cleanup_order_status_lock(order.client_order_id)
                return False

            # Verify the cancel transaction using verification_pool
            signed_tx = submit_result.signed_tx
            prelim_result = submit_result.prelim_result

            # For temBAD_SEQUENCE, the offer was already gone - skip verification
            if prelim_result == "temBAD_SEQUENCE":
                self.logger().debug(
                    f"[CANCEL] Order {order.client_order_id} got temBAD_SEQUENCE - "
                    f"offer was likely already cancelled or filled, skipping verification"
                )
                # Check actual order status
                try:
                    final_status = await self._request_order_status(order)
                    if final_status.new_state == OrderState.CANCELED:
                        await self._process_final_order_state(order, OrderState.CANCELED, self._time())
                        return True
                    elif final_status.new_state == OrderState.FILLED:
                        trade_updates = await self._all_trade_updates_for_order(order)
                        first_trade_update = trade_updates[0] if len(trade_updates) > 0 else None
                        await self._process_final_order_state(
                            order, OrderState.FILLED, final_status.update_timestamp, first_trade_update
                        )
                        for trade_update in trade_updates[1:]:
                            self._order_tracker.process_trade_update(trade_update)
                        return False
                except Exception as e:
                    self.logger().warning(f"Failed to check order status after temBAD_SEQUENCE: {e}")
                # Assume cancelled if we can't verify
                await self._process_final_order_state(order, OrderState.CANCELED, self._time())
                return True

            # Verify using verification_pool
            if submit_result.is_accepted and signed_tx is not None:
                verify_result: TransactionVerifyResult = await self.verification_pool.submit_verification(
                    signed_tx=signed_tx,
                    prelim_result=prelim_result or "tesSUCCESS",
                    timeout=CONSTANTS.VERIFY_TX_TIMEOUT,
                )

                if verify_result.verified and verify_result.response is not None:
                    resp = verify_result.response
                    meta = resp.result.get("meta", {})

                    # Handle case where exchange_order_id might be None
                    if order.exchange_order_id is None:
                        self.logger().error(
                            f"Cannot process cancel for order {order.client_order_id} with None exchange_order_id"
                        )
                        return False

                    sequence, ledger_index, tx_hash_prefix = order.exchange_order_id.split("-")
                    changes_array = get_order_book_changes(meta)
                    changes_array = [x for x in changes_array if x.get("maker_account") == self._xrpl_auth.get_account()]
                    status = "UNKNOWN"

                    for offer_change in changes_array:
                        changes = offer_change.get("offer_changes", [])
                        for found_tx in changes:
                            if int(found_tx.get("sequence")) == int(sequence):
                                status = found_tx.get("status")
                                break

                    if len(changes_array) == 0:
                        status = "cancelled"

                    if status == "cancelled":
                        self.logger().debug(
                            f"[CANCEL] Order {order.client_order_id} successfully canceled "
                            f"(previous state: {order.current_state.name})"
                        )
                        await self._process_final_order_state(order, OrderState.CANCELED, self._time())
                        return True
                    else:
                        # Check if order was actually filled during cancellation attempt
                        try:
                            final_status_check = await self._request_order_status(order)
                            if final_status_check.new_state == OrderState.FILLED:
                                self.logger().debug(
                                    f"[CANCEL_RACE_CONDITION] Order {order.client_order_id} was filled during cancellation attempt "
                                    f"(previous state: {order.current_state.name} -> {final_status_check.new_state.name})"
                                )
                                trade_updates = await self._all_trade_updates_for_order(order)
                                first_trade_update = trade_updates[0] if len(trade_updates) > 0 else None
                                await self._process_final_order_state(
                                    order, OrderState.FILLED, final_status_check.update_timestamp, first_trade_update
                                )
                                for trade_update in trade_updates[1:]:
                                    self._order_tracker.process_trade_update(trade_update)
                                return False  # Cancellation not successful because order filled
                        except Exception as final_check_error:
                            self.logger().warning(
                                f"Failed final status check for order {order.client_order_id}: {final_check_error}"
                            )

                        await self._order_tracker.process_order_not_found(order.client_order_id)
                        await self._cleanup_order_status_lock(order.client_order_id)
                        return False
                else:
                    self.logger().error(
                        f"[CANCEL] Order {order.client_order_id} verification failed: {verify_result.error}"
                    )

            await self._order_tracker.process_order_not_found(order.client_order_id)
            await self._cleanup_order_status_lock(order.client_order_id)
            return False

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        return await super().cancel_all(CONSTANTS.CANCEL_ALL_TIMEOUT)

    def _format_trading_rules(self, trading_rules_info: Dict[str, Any]) -> List[TradingRule]:  # type: ignore
        trading_rules = []
        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_tick_size = trading_pair_info["base_tick_size"]
            quote_tick_size = trading_pair_info["quote_tick_size"]
            minimum_order_size = trading_pair_info["minimum_order_size"]

            trading_rule = TradingRule(
                trading_pair=trading_pair,
                min_order_size=Decimal(minimum_order_size),
                min_price_increment=Decimal(f"1e-{quote_tick_size}"),
                min_quote_amount_increment=Decimal(f"1e-{quote_tick_size}"),
                min_base_amount_increment=Decimal(f"1e-{base_tick_size}"),
                min_notional_size=Decimal(f"1e-{quote_tick_size}"),
            )

            trading_rules.append(trading_rule)

        return trading_rules

    def _format_trading_pair_fee_rules(self, trading_rules_info: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        trading_pair_fee_rules = []

        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_token = trading_pair.split("-")[0]
            quote_token = trading_pair.split("-")[1]
            amm_pool_info: PoolInfo | None = trading_pair_info.get("amm_pool_info", None)

            if amm_pool_info is not None:
                amm_pool_fee = amm_pool_info.fee_pct / Decimal("100")
            else:
                amm_pool_fee = Decimal("0")

            trading_pair_fee_rules.append(
                {
                    "trading_pair": trading_pair,
                    "base_token": base_token,
                    "quote_token": quote_token,
                    "base_transfer_rate": trading_pair_info["base_transfer_rate"],
                    "quote_transfer_rate": trading_pair_info["quote_transfer_rate"],
                    "amm_pool_fee": amm_pool_fee,
                }
            )

        return trading_pair_fee_rules

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        # TODO: Move fee update logic to this method
        pass

    def get_order_by_sequence(self, sequence) -> Optional[InFlightOrder]:
        for client_order_id, order in self._order_tracker.all_fillable_orders.items():
            if order.exchange_order_id is None:
                continue  # Skip orders without exchange_order_id and continue checking others

            if int(order.exchange_order_id.split("-")[0]) == int(sequence):
                return order

        return None

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                transaction = event_message.get("transaction", None)
                meta = event_message.get("meta")

                if transaction is None or meta is None:
                    self.logger().debug(f"Received event message without transaction or meta: {event_message}")
                    continue

                self.logger().debug(
                    f"Handling TransactionType: {transaction.get('TransactionType')}, Hash: {event_message.get('hash')} OfferSequence: {transaction.get('OfferSequence')}, Sequence: {transaction.get('Sequence')}"
                )

                order_book_changes = get_order_book_changes(meta)

                # Check if this is market order, if it is, check if it has been filled or failed
                tx_sequence = transaction.get("Sequence")
                tracked_order = self.get_order_by_sequence(tx_sequence)

                if (
                    tracked_order is not None
                    and tracked_order.order_type in [OrderType.MARKET, OrderType.AMM_SWAP]
                    and tracked_order.current_state in [OrderState.OPEN]
                ):
                    self.logger().debug(
                        f"[ORDER] User stream event for {tracked_order.order_type.name} order "
                        f"{tracked_order.client_order_id}: tx_type={transaction.get('TransactionType')}"
                    )
                    await self._process_market_order_transaction(tracked_order, transaction, meta, event_message)

                # Handle order book changes for limit orders and other order types
                await self._process_order_book_changes(order_book_changes, transaction, event_message)

                # Handle balance updates using final balances (absolute values) instead of delta changes
                # This prevents race conditions where delta-based updates can cause temporary negative balances
                final_balances = get_final_balances(meta)
                our_final_balances = [fb for fb in final_balances if fb["account"] == self._xrpl_auth.get_account()]

                if our_final_balances:
                    self.logger().debug(
                        f"[BALANCE] Processing final balances from tx: "
                        f"{transaction.get('TransactionType')} hash={event_message.get('hash', 'unknown')[:16]}..."
                    )

                for final_balance in our_final_balances:
                    self.logger().debug(f"[BALANCE] Final balance data: {final_balance}")

                    for balance in final_balance["balances"]:
                        raw_currency = balance["currency"]
                        currency = raw_currency
                        absolute_value = Decimal(balance["value"])

                        # Convert hex currency code to string if needed
                        if len(currency) > 3:
                            try:
                                currency = hex_to_str(currency).strip("\x00").upper()
                            except UnicodeDecodeError:
                                # Do nothing since this is a non-hex string
                                pass

                        self.logger().debug(
                            f"[BALANCE] Final balance: raw_currency={raw_currency}, "
                            f"decoded_currency={currency}, absolute_value={absolute_value}"
                        )

                        # For XRP, update both total and available balances
                        if currency == "XRP":
                            if self._account_balances is None:
                                self._account_balances = {}
                            if self._account_available_balances is None:
                                self._account_available_balances = {}

                            # Get previous values for logging
                            previous_total = self._account_balances.get(currency, Decimal("0"))
                            previous_available = self._account_available_balances.get(currency, Decimal("0"))

                            # Set total balance to the absolute final value
                            self._account_balances[currency] = absolute_value

                            # Calculate available balance = total - locked
                            # Floor to 0 to handle race conditions where order tracker hasn't updated yet
                            locked = self._calculate_locked_balance_for_token(currency)
                            new_available = max(Decimal("0"), absolute_value - locked)
                            self._account_available_balances[currency] = new_available

                            # Log the balance update
                            self.logger().debug(
                                f"[BALANCE] {currency} updated: total {previous_total:.6f} -> {absolute_value:.6f}, "
                                f"available {previous_available:.6f} -> {new_available:.6f} (locked: {locked:.6f})"
                            )
                        else:
                            # For other tokens, we need to get the token symbol
                            # Use the issuer from the balance object, not the account
                            token_symbol = self.get_token_symbol_from_all_markets(
                                currency, balance.get("issuer", "")
                            )
                            if token_symbol is not None:
                                if self._account_balances is None:
                                    self._account_balances = {}
                                if self._account_available_balances is None:
                                    self._account_available_balances = {}

                                # Get previous values for logging
                                previous_total = self._account_balances.get(token_symbol, Decimal("0"))
                                previous_available = self._account_available_balances.get(token_symbol, Decimal("0"))

                                # Set total balance to the absolute final value
                                self._account_balances[token_symbol] = absolute_value

                                # Calculate available balance = total - locked
                                # Floor to 0 to handle race conditions where order tracker hasn't updated yet
                                locked = self._calculate_locked_balance_for_token(token_symbol)
                                new_available = max(Decimal("0"), absolute_value - locked)
                                self._account_available_balances[token_symbol] = new_available

                                # Log the balance update
                                self.logger().debug(
                                    f"[BALANCE] {token_symbol} updated: total {previous_total:.6f} -> {absolute_value:.6f}, "
                                    f"available {previous_available:.6f} -> {new_available:.6f} (locked: {locked:.6f})"
                                )
                            else:
                                self.logger().debug(
                                    f"[BALANCE] Skipping unknown token: currency={currency}, "
                                    f"issuer={balance.get('issuer', 'unknown')}, value={absolute_value}"
                                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        try:
            exchange_order_id = await order.get_exchange_order_id()
        except asyncio.TimeoutError:
            self.logger().warning(f"Skipped order update with fills for {order.client_order_id} - waiting for exchange order id.")
            return []

        assert exchange_order_id is not None

        _, ledger_index, _ = exchange_order_id.split("-")

        transactions = await self._fetch_account_transactions(int(ledger_index), is_forward=True)

        trade_fills = []

        for transaction in transactions:
            tx = transaction.get("tx") or transaction.get("transaction") or transaction.get("tx_json")

            if tx is None:
                self.logger().debug(f"Transaction not found for order {order.client_order_id}, data: {transaction}")
                continue

            tx_type = tx.get("TransactionType", None)

            if tx_type is None or tx_type not in ["OfferCreate", "Payment"]:
                self.logger().debug(
                    f"Skipping transaction with type {tx_type} for order {order.client_order_id} ({order.exchange_order_id})"
                )
                continue

            trade_update = await self.process_trade_fills(transaction, order)
            if trade_update is not None:
                trade_fills.append(trade_update)

        return trade_fills

    # ==================== Trade Fill Processing Helper Methods ====================

    def _get_fee_for_order(self, order: InFlightOrder, fee_rules: Dict[str, Any]) -> Optional[TradeFeeBase]:
        """
        Calculate the fee for an order based on fee rules.

        Args:
            order: The order to calculate fee for
            fee_rules: Fee rules for the trading pair

        Returns:
            TradeFee object or None if fee cannot be calculated
        """
        if order.trade_type is TradeType.BUY:
            fee_token = fee_rules.get("quote_token")
            fee_rate = fee_rules.get("quote_transfer_rate")
        else:
            fee_token = fee_rules.get("base_token")
            fee_rate = fee_rules.get("base_transfer_rate")

        if order.order_type == OrderType.AMM_SWAP:
            fee_rate = fee_rules.get("amm_pool_fee")

        if fee_token is None or fee_rate is None:
            return None

        return TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=fee_token.upper(),
            percent=Decimal(str(fee_rate)),
        )

    def _create_trade_update(
        self,
        order: InFlightOrder,
        tx_hash: str,
        tx_date: int,
        base_amount: Decimal,
        quote_amount: Decimal,
        fee: TradeFeeBase,
        offer_sequence: Optional[int] = None,
    ) -> TradeUpdate:
        """
        Create a TradeUpdate object.

        Args:
            order: The order being filled
            tx_hash: Transaction hash
            tx_date: Transaction date (ripple time)
            base_amount: Filled base amount (absolute value)
            quote_amount: Filled quote amount (absolute value)
            fee: Trade fee
            offer_sequence: Optional sequence for unique trade ID when multiple fills

        Returns:
            TradeUpdate object
        """
        # Create unique trade ID - append sequence if this is a maker fill
        trade_id = tx_hash
        if offer_sequence is not None:
            trade_id = f"{tx_hash}_{offer_sequence}"

        fill_price = quote_amount / base_amount if base_amount > 0 else Decimal("0")

        return TradeUpdate(
            trade_id=trade_id,
            client_order_id=order.client_order_id,
            exchange_order_id=str(order.exchange_order_id),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=base_amount,
            fill_quote_amount=quote_amount,
            fill_price=fill_price,
            fill_timestamp=ripple_time_to_posix(tx_date),
        )

    # ==================== Main Trade Fill Processing Method ====================

    async def process_trade_fills(self, data: Optional[Dict[str, Any]], order: InFlightOrder) -> Optional[TradeUpdate]:
        """
        Process trade fills from transaction data.

        This method handles:
        1. Market orders / AMM swaps - uses balance changes as source of truth
        2. Limit orders that cross existing offers (taker fills) - uses balance changes
        3. Limit orders filled by external transactions (maker fills) - uses offer changes

        Args:
            data: Transaction data containing meta and tx information
            order: The order to process fills for

        Returns:
            TradeUpdate if a fill was processed, None otherwise
        """
        # Validate inputs
        if data is None:
            self.logger().error(f"Data is None for order {order.client_order_id}")
            raise ValueError(f"Data is None for order {order.client_order_id}")

        try:
            exchange_order_id = await order.get_exchange_order_id()
        except asyncio.TimeoutError:
            self.logger().warning(f"Skipped process trade fills for {order.client_order_id} - waiting for exchange order id.")
            return None

        assert exchange_order_id is not None

        # Extract order sequence
        sequence, _, tx_hash_prefix = exchange_order_id.split("-")
        order_sequence = int(sequence)

        # Get currencies
        base_currency, quote_currency = self.get_currencies_from_trading_pair(order.trading_pair)

        # Get fee rules
        fee_rules = self._trading_pair_fee_rules.get(order.trading_pair)
        if fee_rules is None:
            await self._update_trading_rules()
            fee_rules = self._trading_pair_fee_rules.get(order.trading_pair)
            if fee_rules is None:
                self.logger().error(
                    f"Fee rules not found for order {order.client_order_id} ({order.exchange_order_id}), "
                    f"trading_pair: {order.trading_pair}"
                )
                raise ValueError(f"Fee rules not found for order {order.client_order_id}")

        # Extract transaction and metadata
        tx, meta = extract_transaction_data(data)
        if tx is None:
            self.logger().error(
                f"Transaction not found for order {order.client_order_id} ({order.exchange_order_id}), data: {data}"
            )
            return None

        # Validate transaction type
        if tx.get("TransactionType") not in ["OfferCreate", "Payment"]:
            self.logger().debug(
                f"Skipping non-trade transaction type {tx.get('TransactionType')} for order "
                f"{order.client_order_id} ({order.exchange_order_id})"
            )
            return None

        # Validate required fields
        tx_hash = tx.get("hash")
        tx_date = tx.get("date")
        tx_sequence = tx.get("Sequence")

        if tx_hash is None:
            self.logger().error(
                f"Transaction hash is None for order {order.client_order_id} ({order.exchange_order_id})"
            )
            return None

        if tx_date is None:
            self.logger().error(
                f"Transaction date is None for order {order.client_order_id} ({order.exchange_order_id})"
            )
            return None

        # Check transaction status
        tx_status = meta.get("TransactionResult")
        if tx_status != "tesSUCCESS":
            self.logger().debug(f"Transaction not successful for order {order.client_order_id}: {tx_status}")
            return None

        # Use xrpl-py parsers to get changes
        # Cast to Any to work with xrpl-py's TransactionMetadata type
        offer_changes = get_order_book_changes(cast(Any, meta))
        balance_changes = get_balance_changes(cast(Any, meta))

        # Filter to our account only
        our_account = self._xrpl_auth.get_account()
        our_offer_changes = [x for x in offer_changes if x.get("maker_account") == our_account]
        our_balance_changes = [x for x in balance_changes if x.get("account") == our_account]

        # Debug logging: Log all offer changes and balance changes
        self.logger().debug(
            f"[TRADE_FILL_DEBUG] {tx_hash}, order={order.client_order_id}, "
            f"offer_changes={len(our_offer_changes)}/{len(offer_changes)}, "
            f"balance_changes={len(our_balance_changes)}/{len(balance_changes)}"
        )
        for i, oc in enumerate(our_offer_changes):
            oc_changes = oc.get("offer_changes", [])
            for j, change in enumerate(oc_changes):
                self.logger().debug(
                    f"[TRADE_FILL_DEBUG] offer[{i}][{j}]: seq={change.get('sequence')}, "
                    f"status={change.get('status')}, gets={change.get('taker_gets')}, pays={change.get('taker_pays')}"
                )

        # Calculate fee
        fee = self._get_fee_for_order(order, fee_rules)
        if fee is None:
            self.logger().error(f"Could not calculate fee for order {order.client_order_id}")
            return None

        # Determine if this is our transaction (we're the taker) or external (we're the maker)
        incoming_tx_hash_prefix = tx_hash[0:len(tx_hash_prefix)]
        is_our_transaction = (
            tx_sequence is not None and int(tx_sequence) == order_sequence and incoming_tx_hash_prefix == tx_hash_prefix
        )

        self.logger().debug(
            f"[TRADE_FILL] {tx_hash}, order={order.client_order_id}, "
            f"tx_seq={tx_sequence}, order_seq={order_sequence}, is_taker={is_our_transaction}"
        )

        if is_our_transaction:
            # We initiated this transaction - we're the taker
            # Use balance changes as the source of truth
            return await self._process_taker_fill(
                order=order,
                tx=tx,
                tx_hash=tx_hash,
                tx_date=tx_date,
                our_offer_changes=our_offer_changes,
                our_balance_changes=our_balance_changes,
                base_currency=base_currency.currency,
                quote_currency=quote_currency.currency,
                fee=fee,
                order_sequence=order_sequence,
            )
        else:
            # External transaction filled our offer - we're the maker
            return await self._process_maker_fill(
                order=order,
                tx_hash=tx_hash,
                tx_date=tx_date,
                our_offer_changes=our_offer_changes,
                base_currency=base_currency.currency,
                quote_currency=quote_currency.currency,
                fee=fee,
                order_sequence=order_sequence,
            )

    async def _process_taker_fill(
        self,
        order: InFlightOrder,
        tx: Dict[str, Any],
        tx_hash: str,
        tx_date: int,
        our_offer_changes: Any,
        our_balance_changes: Any,
        base_currency: str,
        quote_currency: str,
        fee: TradeFeeBase,
        order_sequence: int,
    ) -> Optional[TradeUpdate]:
        """
        Process a fill where we initiated the transaction (taker fill).

        For market orders and limit orders that cross existing offers.

        Handles several scenarios:
        - Market orders: Always use balance changes to extract fill amounts
        - Limit orders that cross existing offers:
            - "filled"/"partially-filled" status: Extract from offer change delta
            - "created" status: Order partially filled on creation, remainder placed on book.
              Fill amount extracted from balance changes.
            - "cancelled" status: Order partially filled on creation, but remainder was cancelled
              (e.g., due to tecUNFUNDED_OFFER or tecINSUF_RESERVE_OFFER after partial fill).
              Fill amount extracted from balance changes.

        Args:
            order: The order being filled
            tx: Transaction data
            tx_hash: Transaction hash
            tx_date: Transaction date
            our_offer_changes: Offer changes for our account
            our_balance_changes: Balance changes for our account
            base_currency: Base currency code
            quote_currency: Quote currency code
            fee: Trade fee
            order_sequence: Our order's sequence number

        Returns:
            TradeUpdate if fill processed, None otherwise
        """
        # For market orders or AMM swaps, always use balance changes
        if order.order_type in [OrderType.MARKET, OrderType.AMM_SWAP]:
            base_amount, quote_amount = extract_fill_amounts_from_balance_changes(
                our_balance_changes, base_currency, quote_currency
            )

            if base_amount is None or quote_amount is None or base_amount == Decimal("0"):
                self.logger().debug(
                    f"No valid fill amounts from balance changes for market order {order.client_order_id}"
                )
                return None

            self.logger().debug(
                f"[FILL] {order.order_type.name} order {order.client_order_id} filled: "
                f"{base_amount} @ {quote_amount / base_amount if base_amount > 0 else 0:.8f} = {quote_amount} "
                f"(trade_type: {order.trade_type.name})"
            )

            return self._create_trade_update(
                order=order,
                tx_hash=tx_hash,
                tx_date=tx_date,
                base_amount=base_amount,
                quote_amount=quote_amount,
                fee=fee,
            )

        # For limit orders, check if we have an offer change for our order
        # Include "created" and "cancelled" status to detect partial fills on order creation
        matching_offer = find_offer_change_for_order(our_offer_changes, order_sequence, include_created=True)

        # Log the state for debugging
        offer_sequences_in_changes = []
        for oc in our_offer_changes:
            for change in oc.get("offer_changes", []):
                offer_sequences_in_changes.append(f"{change.get('sequence')}:{change.get('status')}")
        self.logger().debug(
            f"[TAKER_FILL] Processing order {order.client_order_id} (seq={order_sequence}): "
            f"matching_offer={'found' if matching_offer else 'None'}, "
            f"our_offer_changes_count={len(our_offer_changes)}, "
            f"offer_sequences={offer_sequences_in_changes}, "
            f"our_balance_changes_count={len(our_balance_changes)}"
        )

        if matching_offer is not None:
            offer_status = matching_offer.get("status")

            if offer_status in ["created", "cancelled"]:
                # Our order was partially filled on creation:
                # - "created": remaining amount went on the book as a new offer
                # - "cancelled": remaining amount was cancelled (e.g., tecUNFUNDED_OFFER or tecINSUF_RESERVE_OFFER
                #   after partial fill - the order traded some amount but couldn't place the remainder)
                # The fill amount comes from balance changes, not the offer change
                # (offer change with "created"/"cancelled" status shows what's LEFT/CANCELLED, not what was FILLED)
                if len(our_balance_changes) > 0:
                    base_amount, quote_amount = extract_fill_amounts_from_balance_changes(
                        our_balance_changes, base_currency, quote_currency
                    )
                    if base_amount is not None and quote_amount is not None and base_amount > Decimal("0"):
                        remainder_action = "placed on book" if offer_status == "created" else "cancelled"
                        self.logger().debug(
                            f"[FILL] LIMIT order {order.client_order_id} taker fill (partial fill on creation, remainder {remainder_action}): "
                            f"{base_amount} @ {quote_amount / base_amount:.8f} = {quote_amount} "
                            f"(trade_type: {order.trade_type.name}, offer_status: {offer_status})"
                        )
                        return self._create_trade_update(
                            order=order,
                            tx_hash=tx_hash,
                            tx_date=tx_date,
                            base_amount=base_amount,
                            quote_amount=quote_amount,
                            fee=fee,
                        )
                # No balance changes - order went on book without fill (created) or was cancelled without any fill
                if offer_status == "created":
                    self.logger().debug(
                        f"[ORDER] Order {order.client_order_id} placed on book without immediate fill "
                        f"(offer_status: created, no balance changes)"
                    )
                else:
                    self.logger().debug(
                        f"[ORDER] Order {order.client_order_id} cancelled without any fill "
                        f"(offer_status: cancelled, no balance changes)"
                    )
                return None

            elif offer_status in ["filled", "partially-filled"]:
                # Our limit order was created AND partially/fully crossed existing offers
                # Use the offer change delta for the fill amount
                base_amount, quote_amount = extract_fill_amounts_from_offer_change(
                    matching_offer, base_currency, quote_currency
                )

                if base_amount is not None and quote_amount is not None and base_amount > Decimal("0"):
                    self.logger().debug(
                        f"[FILL] LIMIT order {order.client_order_id} taker fill (crossed offers): "
                        f"{base_amount} @ {quote_amount / base_amount:.8f} = {quote_amount} "
                        f"(trade_type: {order.trade_type.name})"
                    )
                    return self._create_trade_update(
                        order=order,
                        tx_hash=tx_hash,
                        tx_date=tx_date,
                        base_amount=base_amount,
                        quote_amount=quote_amount,
                        fee=fee,
                    )

        # No offer changes for our sequence - check if there are balance changes
        # This happens when a limit order is immediately fully filled (never hits the book)
        # Note: our_offer_changes may contain changes for OTHER offers on our account that got
        # consumed by this same transaction, so we check matching_offer (not our_offer_changes length)
        if matching_offer is None and len(our_balance_changes) > 0:
            self.logger().debug(
                f"[TAKER_FILL] Order {order.client_order_id} (seq={order_sequence}): "
                f"no matching offer change found, using balance changes for fully-filled order"
            )
            base_amount, quote_amount = extract_fill_amounts_from_balance_changes(
                our_balance_changes, base_currency, quote_currency
            )

            if base_amount is not None and quote_amount is not None and base_amount > Decimal("0"):
                self.logger().debug(
                    f"[FILL] LIMIT order {order.client_order_id} taker fill (fully filled, never hit book): "
                    f"{base_amount} @ {quote_amount / base_amount:.8f} = {quote_amount} "
                    f"(trade_type: {order.trade_type.name})"
                )
                return self._create_trade_update(
                    order=order,
                    tx_hash=tx_hash,
                    tx_date=tx_date,
                    base_amount=base_amount,
                    quote_amount=quote_amount,
                    fee=fee,
                )
            else:
                self.logger().warning(
                    f"[TAKER_FILL] Order {order.client_order_id} (seq={order_sequence}): "
                    f"balance changes present but could not extract valid fill amounts: "
                    f"base={base_amount}, quote={quote_amount}"
                )
                # Fallback: Try to extract fill amounts from transaction's TakerGets/TakerPays
                # This handles dust orders where balance changes are incomplete (amounts too small
                # to be recorded on the ledger). For fully consumed orders with tesSUCCESS,
                # the TakerGets/TakerPays represent the exact traded amounts.
                self.logger().debug(
                    f"[TAKER_FILL] Order {order.client_order_id} (seq={order_sequence}): "
                    f"attempting fallback extraction from transaction TakerGets/TakerPays"
                )
                base_amount, quote_amount = extract_fill_amounts_from_transaction(
                    tx, base_currency, quote_currency, order.trade_type
                )
                if base_amount is not None and quote_amount is not None and base_amount > Decimal("0"):
                    self.logger().debug(
                        f"[FILL] LIMIT order {order.client_order_id} taker fill (from tx TakerGets/TakerPays): "
                        f"{base_amount} @ {quote_amount / base_amount:.8f} = {quote_amount} "
                        f"(trade_type: {order.trade_type.name})"
                    )
                    return self._create_trade_update(
                        order=order,
                        tx_hash=tx_hash,
                        tx_date=tx_date,
                        base_amount=base_amount,
                        quote_amount=quote_amount,
                        fee=fee,
                    )
                else:
                    self.logger().warning(
                        f"[TAKER_FILL] Order {order.client_order_id} (seq={order_sequence}): "
                        f"fallback extraction from TakerGets/TakerPays also failed: "
                        f"base={base_amount}, quote={quote_amount}"
                    )

        self.logger().debug(
            f"[TAKER_FILL] No fill detected for order {order.client_order_id} (seq={order_sequence}) in tx {tx_hash}: "
            f"matching_offer={matching_offer is not None}, balance_changes_count={len(our_balance_changes)}"
        )
        return None

    async def _process_maker_fill(
        self,
        order: InFlightOrder,
        tx_hash: str,
        tx_date: int,
        our_offer_changes: Any,
        base_currency: str,
        quote_currency: str,
        fee: TradeFeeBase,
        order_sequence: int,
    ) -> Optional[TradeUpdate]:
        """
        Process a fill where an external transaction filled our offer (maker fill).

        Args:
            order: The order being filled
            tx_hash: Transaction hash
            tx_date: Transaction date
            our_offer_changes: Offer changes for our account
            base_currency: Base currency code
            quote_currency: Quote currency code
            fee: Trade fee
            order_sequence: Our order's sequence number

        Returns:
            TradeUpdate if fill processed, None otherwise
        """
        self.logger().debug(
            f"[MAKER_FILL_DEBUG] {tx_hash}, order={order.client_order_id}, seq={order_sequence}, "
            f"offer_changes={len(our_offer_changes)}"
        )

        # Find the offer change matching our order
        matching_offer = find_offer_change_for_order(our_offer_changes, order_sequence)

        if matching_offer is None:
            self.logger().debug(
                f"[MAKER_FILL_DEBUG] No match for seq={order_sequence} in {tx_hash}"
            )
            return None

        self.logger().debug(
            f"[MAKER_FILL_DEBUG] Match: seq={matching_offer.get('sequence')}, status={matching_offer.get('status')}, "
            f"gets={matching_offer.get('taker_gets')}, pays={matching_offer.get('taker_pays')}"
        )

        # Extract fill amounts from the offer change
        base_amount, quote_amount = extract_fill_amounts_from_offer_change(matching_offer, base_currency, quote_currency)

        self.logger().debug(f"[MAKER_FILL_DEBUG] Extracted: base={base_amount}, quote={quote_amount}")

        if base_amount is None or quote_amount is None or base_amount == Decimal("0"):
            self.logger().debug(
                f"[MAKER_FILL_DEBUG] Invalid amounts for {order.client_order_id}: base={base_amount}, quote={quote_amount}"
            )
            return None

        self.logger().debug(
            f"[FILL] LIMIT order {order.client_order_id} maker fill: "
            f"{base_amount} @ {quote_amount / base_amount:.8f} = {quote_amount} "
            f"(trade_type: {order.trade_type.name}, offer_status: {matching_offer.get('status')})"
        )

        # Use unique trade ID with sequence to handle multiple fills from same tx
        return self._create_trade_update(
            order=order,
            tx_hash=tx_hash,
            tx_date=tx_date,
            base_amount=base_amount,
            quote_amount=quote_amount,
            fee=fee,
            offer_sequence=order_sequence,
        )

    async def _request_order_status(
        self, tracked_order: InFlightOrder, creation_tx_resp: Optional[Dict] = None
    ) -> OrderUpdate:
        new_order_state = tracked_order.current_state
        latest_status = "UNKNOWN"

        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
        except asyncio.TimeoutError:
            self.logger().warning(f"Skipped request order status for {tracked_order.client_order_id} - waiting for exchange order id.")
            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=tracked_order.current_state,
            )

        assert exchange_order_id is not None

        sequence, ledger_index, tx_hash_prefix = exchange_order_id.split("-")
        found_creation_tx = None
        found_creation_meta = None
        found_txs = []

        # Only fetch history if we don't have the creation response
        # This avoids an expensive ~8-9s fetch for market orders where we already have the data
        if creation_tx_resp is None:
            transactions = await self._fetch_account_transactions(int(ledger_index))
        else:
            transactions = [creation_tx_resp]

        for transaction in transactions:
            if "result" in transaction:
                data_result = transaction.get("result", {})
                meta = data_result.get("meta", {})
                tx = data_result
            else:
                meta = transaction.get("meta", {})
                tx = (
                    transaction.get("tx") or transaction.get("transaction") or transaction.get("tx_json") or transaction
                )

            if tx is not None and tx.get("Sequence", 0) == int(sequence):
                found_creation_tx = tx
                found_creation_meta = meta

            # Get ledger_index from either tx object or transaction wrapper (AccountTx returns it at wrapper level)
            tx_ledger_index = tx.get("ledger_index") if tx else None
            if tx_ledger_index is None:
                tx_ledger_index = transaction.get("ledger_index", 0)

            found_txs.append(
                {
                    "meta": meta,
                    "tx": tx,
                    "sequence": tx.get("Sequence", 0) if tx else 0,
                    "ledger_index": tx_ledger_index,
                }
            )

        if found_creation_meta is None or found_creation_tx is None:
            current_state = tracked_order.current_state
            if current_state is OrderState.PENDING_CREATE or current_state is OrderState.PENDING_CANCEL:
                if time.time() - tracked_order.last_update_timestamp > CONSTANTS.PENDING_ORDER_STATUS_CHECK_TIMEOUT:
                    new_order_state = OrderState.FAILED
                    self.logger().debug(f"Transactions searched: {transactions}")
                    self.logger().debug(f"Creation tx resp: {creation_tx_resp}")
                    self.logger().error(
                        f"Order status not found for order {tracked_order.client_order_id} ({sequence}), tx history: {transactions}"
                    )
                else:
                    new_order_state = current_state
            else:
                new_order_state = current_state

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_order_state,
            )

            return order_update

        # Process order by found_meta and found_tx
        if tracked_order.order_type in [OrderType.MARKET, OrderType.AMM_SWAP]:
            tx_status = found_creation_meta.get("TransactionResult")
            update_timestamp = time.time()
            if tx_status != "tesSUCCESS":
                new_order_state = OrderState.FAILED
                self.logger().error(
                    f"Order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}) failed: {tx_status}, meta: {found_creation_meta}, tx: {found_creation_tx}"
                )
            else:
                new_order_state = OrderState.FILLED

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=new_order_state,
            )

            return order_update
        else:
            # Track the latest status by ledger index (chronologically newest)
            # This ensures we get the final state even if transactions are returned in any order
            latest_status = "UNKNOWN"
            latest_ledger_index = -1
            found = False

            for tx in found_txs:
                meta = tx.get("meta", {})
                tx_ledger_index = tx.get("ledger_index", 0)

                changes_array = get_order_book_changes(meta)
                # Filter out change that is not from this account
                changes_array = [x for x in changes_array if x.get("maker_account") == self._xrpl_auth.get_account()]

                for offer_change in changes_array:
                    changes = offer_change.get("offer_changes", [])

                    for found_tx in changes:
                        if int(found_tx.get("sequence")) == int(sequence):
                            # Only update if this transaction is from a later ledger (chronologically newer)
                            if tx_ledger_index > latest_ledger_index:
                                latest_status = found_tx.get("status")
                                latest_ledger_index = tx_ledger_index
                                found = True
                            break  # Found our sequence in this tx, move to next tx

            if found:
                self.logger().debug(
                    f"[ORDER_STATUS] Order {tracked_order.client_order_id} (seq={sequence}): "
                    f"latest_status={latest_status} from ledger {latest_ledger_index}, "
                    f"total_txs_searched={len(found_txs)}"
                )
            else:
                self.logger().debug(
                    f"[ORDER_STATUS] Order {tracked_order.client_order_id} (seq={sequence}): "
                    f"no matching offer_changes found in {len(found_txs)} transactions"
                )

            if found is False:
                # TODO: Only make this check if this is a at order creation
                # No offer created, this look like the order has been consumed without creating any offer object
                # Check if there is any balance changes
                balance_changes = get_balance_changes(found_creation_meta)

                # Filter by account
                balance_changes = [x for x in balance_changes if x.get("account") == self._xrpl_auth.get_account()]

                # If there is balance change for the account, this order has been filled
                if len(balance_changes) > 0:
                    new_order_state = OrderState.FILLED
                else:
                    new_order_state = OrderState.FAILED
            elif latest_status == "filled":
                new_order_state = OrderState.FILLED
            elif latest_status == "partially-filled":
                new_order_state = OrderState.PARTIALLY_FILLED
            elif latest_status == "cancelled":
                new_order_state = OrderState.CANCELED
            elif latest_status == "created":
                # Check if there were TOKEN balance changes (not XRP) indicating a partial fill alongside offer creation.
                # This happens when an order partially crosses the book and the remainder is placed on book.
                # In this case, offer_changes shows "created" but balance_changes indicate a fill occurred.
                # Note: We must filter out XRP-only balance changes as those are just fee deductions, not fills.
                creation_balance_changes = get_balance_changes(found_creation_meta)
                our_creation_balance_changes = [
                    x for x in creation_balance_changes if x.get("account") == self._xrpl_auth.get_account()
                ]
                # Check for non-XRP token balance changes (actual fills, not fee deductions)
                has_token_fill = False
                for bc in our_creation_balance_changes:
                    for balance in bc.get("balances", []):
                        if balance.get("currency") != "XRP":
                            has_token_fill = True
                            break
                    if has_token_fill:
                        break

                if has_token_fill:
                    # Partial fill occurred before remainder was placed on book
                    new_order_state = OrderState.PARTIALLY_FILLED
                    self.logger().debug(
                        f"[ORDER_STATUS] Order {tracked_order.client_order_id} detected partial fill at creation "
                        f"(status=created with token balance changes indicating taker fill)"
                    )
                else:
                    new_order_state = OrderState.OPEN

            self.logger().debug(
                f"[ORDER_STATUS] Order {tracked_order.client_order_id} final state: {new_order_state.name} "
                f"(latest_status={latest_status})"
            )

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_order_state,
            )

            return order_update

    async def _update_orders_with_error_handler(self, orders: List[InFlightOrder], error_handler: Callable):
        for order in orders:
            # Use order lock to prevent race conditions with real-time updates
            order_lock = await self._get_order_status_lock(order.client_order_id)

            try:
                async with order_lock:
                    # Skip if order is already in final state to prevent unnecessary updates
                    if order.current_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
                        if order.current_state == OrderState.FILLED:
                            order.completely_filled_event.set()
                            # Clean up lock for completed order
                            await self._cleanup_order_status_lock(order.client_order_id)
                        elif order.current_state == OrderState.CANCELED:
                            # Clean up lock for canceled order
                            await self._cleanup_order_status_lock(order.client_order_id)
                        elif order.current_state == OrderState.FAILED:
                            # Clean up lock for failed order
                            await self._cleanup_order_status_lock(order.client_order_id)
                        continue

                    order_update = await self._request_order_status(tracked_order=order)

                    # Only process update if the new state is different or represents progress
                    if order_update.new_state != order.current_state or order_update.new_state in [
                        OrderState.FILLED,
                        OrderState.PARTIALLY_FILLED,
                        OrderState.CANCELED,
                    ]:

                        # Enhanced logging for debugging race conditions
                        self.logger().debug(
                            f"[PERIODIC_UPDATE] Order {order.client_order_id} state transition: "
                            f"{order.current_state.name} -> {order_update.new_state.name}"
                        )

                        self._order_tracker.process_order_update(order_update)

                        if order_update.new_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                            trade_updates = await self._all_trade_updates_for_order(order)
                            if len(trade_updates) > 0:
                                for trade_update in trade_updates:
                                    self._order_tracker.process_trade_update(trade_update)

                            if order_update.new_state == OrderState.FILLED:
                                order.completely_filled_event.set()
                                # Clean up lock for completed order
                                await self._cleanup_order_status_lock(order.client_order_id)
                            elif order_update.new_state == OrderState.CANCELED:
                                # Clean up lock for canceled order
                                await self._cleanup_order_status_lock(order.client_order_id)

            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                await error_handler(order, request_error)

    async def _fetch_account_transactions(self, ledger_index: int, is_forward: bool = False) -> list:
        """
        Fetches account transactions from the XRPL ledger.

        :param ledger_index: The ledger index to start fetching transactions from.
        :param is_forward: If True, fetches transactions in forward order, otherwise in reverse order.
        :return: A list of transactions.
        """
        try:
            return_transactions = []
            marker = None
            fetching_transactions = True

            while fetching_transactions:
                request = AccountTx(
                    account=self._xrpl_auth.get_account(),
                    ledger_index_min=int(ledger_index) - CONSTANTS.LEDGER_OFFSET,
                    forward=is_forward,
                    marker=marker,
                )

                try:
                    response = await self._query_xrpl(request, priority=RequestPriority.LOW)
                    result = response.result
                    if result is not None:
                        transactions = result.get("transactions", [])
                        return_transactions.extend(transactions)
                        marker = result.get("marker", None)
                        if marker is None:
                            fetching_transactions = False
                    else:
                        fetching_transactions = False
                except (ConnectionError, TimeoutError) as e:
                    self.logger().warning(f"ConnectionError or TimeoutError encountered: {e}")
                    await self._sleep(CONSTANTS.REQUEST_RETRY_INTERVAL)

        except Exception as e:
            self.logger().error(f"Failed to fetch account transactions: {e}")
            return_transactions = []

        return return_transactions

    def _calculate_locked_balance_for_token(self, token_symbol: str) -> Decimal:
        """
        Calculate the total locked balance for a token based on active orders.

        For SELL orders: the base asset is locked (amount - executed_amount_base)
        For BUY orders: the quote asset is locked ((amount - executed_amount_base) * price)

        :param token_symbol: The token symbol to calculate locked balance for
        :return: Total locked amount as Decimal
        """
        locked_amount = Decimal("0")

        for order in self._order_tracker.all_fillable_orders.values():
            # Skip orders that don't have a price (e.g., market orders)
            if order.price is None:
                continue

            remaining_amount = order.amount - order.executed_amount_base

            if remaining_amount <= Decimal("0"):
                continue

            if order.trade_type == TradeType.SELL:
                # For sell orders, the base asset is locked
                if order.base_asset == token_symbol:
                    locked_amount += remaining_amount
            elif order.trade_type == TradeType.BUY:
                # For buy orders, the quote asset is locked
                if order.quote_asset == token_symbol:
                    locked_amount += remaining_amount * order.price

        return locked_amount

    async def _update_balances(self):
        account_address = self._xrpl_auth.get_account()

        # Run all three queries in parallel for faster balance updates
        # These queries are independent and can be executed concurrently
        account_info, objects, account_lines = await asyncio.gather(
            self._query_xrpl(
                AccountInfo(account=account_address, ledger_index="validated"),
                priority=RequestPriority.LOW,
            ),
            self._query_xrpl(
                AccountObjects(account=account_address),
                priority=RequestPriority.LOW,
            ),
            self._query_xrpl(
                AccountLines(account=account_address),
                priority=RequestPriority.LOW,
            ),
        )

        open_offers = [x for x in objects.result.get("account_objects", []) if x.get("LedgerEntryType") == "Offer"]

        if account_lines is not None:
            balances = account_lines.result.get("lines", [])
        else:
            balances = []

        # DEBUG LOG - DELETE LATER
        self.logger().debug(f"[DEBUG_BALANCE] Raw account_lines count: {len(balances)}")

        xrp_balance = account_info.result.get("account_data", {}).get("Balance", "0")
        total_xrp = drops_to_xrp(xrp_balance)
        total_ledger_objects = len(objects.result.get("account_objects", []))
        available_xrp = total_xrp - CONSTANTS.WALLET_RESERVE - total_ledger_objects * CONSTANTS.LEDGER_OBJECT_RESERVE

        # Always set XRP balance from latest account_info
        account_balances = {
            "XRP": Decimal(total_xrp),
        }

        # If balances is not empty, update token balances as usual
        if len(balances) > 0:
            for balance in balances:
                currency = balance.get("currency")
                raw_currency = currency  # DEBUG - keep original for logging
                if len(currency) > 3:
                    try:
                        currency = hex_to_str(currency)
                    except UnicodeDecodeError:
                        # Do nothing since this is a non-hex string
                        pass

                token = currency.strip("\x00").upper()
                token_issuer = balance.get("account")
                token_symbol = self.get_token_symbol_from_all_markets(token, token_issuer)

                amount = balance.get("balance")

                # DEBUG LOG - DELETE LATER
                self.logger().debug(
                    f"[DEBUG_BALANCE] Processing: raw_currency={raw_currency}, "
                    f"decoded_token={token}, issuer={token_issuer}, "
                    f"resolved_symbol={token_symbol}, amount={amount}"
                )

                if token_symbol is None:
                    continue

                account_balances[token_symbol] = abs(Decimal(amount))
        # If balances is empty, fallback to previous token balances (but not XRP)
        elif self._account_balances is not None:
            for token, amount in self._account_balances.items():
                if token != "XRP":
                    account_balances[token] = amount

        account_available_balances = account_balances.copy()
        account_available_balances["XRP"] = Decimal(available_xrp)

        for offer in open_offers:
            taker_gets = offer.get("TakerGets")
            taker_gets_funded = offer.get("taker_gets_funded", None)

            if taker_gets_funded is not None:
                if isinstance(taker_gets_funded, dict):
                    token = taker_gets_funded.get("currency", "")
                    token_issuer = taker_gets_funded.get("issuer", "")
                    if token and len(token) > 3:
                        token = hex_to_str(token).strip("\x00").upper()
                    token_symbol = self.get_token_symbol_from_all_markets(token or "", token_issuer or "")
                    amount = Decimal(taker_gets_funded.get("value", "0"))
                else:
                    amount = drops_to_xrp(taker_gets_funded)
                    token_symbol = "XRP"
            else:
                if isinstance(taker_gets, dict):
                    token = taker_gets.get("currency", "")
                    token_issuer = taker_gets.get("issuer", "")
                    if token and len(token) > 3:
                        token = hex_to_str(token).strip("\x00").upper()
                    token_symbol = self.get_token_symbol_from_all_markets(token or "", token_issuer or "")
                    amount = Decimal(taker_gets.get("value", "0"))
                else:
                    amount = drops_to_xrp(taker_gets)
                    token_symbol = "XRP"

            if token_symbol is None:
                continue

            account_available_balances[token_symbol] -= amount

        # Clear existing dictionaries to prevent reference retention
        if self._account_balances is not None:
            self._account_balances.clear()
            self._account_balances.update(account_balances)
        else:
            self._account_balances = account_balances

        if self._account_available_balances is not None:
            self._account_available_balances.clear()
            self._account_available_balances.update(account_available_balances)
        else:
            self._account_available_balances = account_available_balances

        # Log periodic balance refresh summary
        balance_summary = ", ".join([f"{k}: {v:.6f}" for k, v in account_available_balances.items()])
        self.logger().debug(f"[BALANCE] Periodic refresh complete: {balance_summary}")

        # DEBUG LOG - DELETE LATER
        self.logger().debug(f"[DEBUG_BALANCE] Final _account_available_balances: {self._account_available_balances}")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, XRPLMarket]):
        markets = exchange_info
        mapping_symbol = bidict()

        for market, _ in markets.items():
            self.logger().debug(f"Processing market {market}")
            mapping_symbol[market.upper()] = market.upper()
        self._set_trading_pair_symbol_map(mapping_symbol)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        # NOTE: We are querying both the order book and the AMM pool to get the last traded price
        last_traded_price = float(0)
        last_traded_price_timestamp = 0

        order_book = self.order_books.get(trading_pair)
        data_source: XRPLAPIOrderBookDataSource = self.order_book_tracker.data_source

        if order_book is not None:
            order_book_last_trade_price = order_book.last_trade_price
            last_traded_price = (
                order_book_last_trade_price
                if order_book_last_trade_price is not None and not math.isnan(order_book_last_trade_price)
                else float(0)
            )
            last_traded_price_timestamp = data_source.last_parsed_order_book_timestamp.get(trading_pair, 0)

        if (math.isnan(last_traded_price) or last_traded_price == 0) and order_book is not None:
            best_bid = order_book.get_price(is_buy=True)
            best_ask = order_book.get_price(is_buy=False)

            is_best_bid_valid = best_bid is not None and not math.isnan(best_bid)
            is_best_ask_valid = best_ask is not None and not math.isnan(best_ask)

            if is_best_bid_valid and is_best_ask_valid:
                last_traded_price = (best_bid + best_ask) / 2
                last_traded_price_timestamp = data_source.last_parsed_order_book_timestamp.get(trading_pair, 0)
            else:
                last_traded_price = float(0)
                last_traded_price_timestamp = 0
        amm_pool_price, amm_pool_last_tx_timestamp = await self.get_price_from_amm_pool(trading_pair)

        if not math.isnan(amm_pool_price):
            if amm_pool_last_tx_timestamp > last_traded_price_timestamp:
                last_traded_price = amm_pool_price
            elif math.isnan(last_traded_price):
                last_traded_price = amm_pool_price
        return last_traded_price

    async def _get_best_price(self, trading_pair: str, is_buy: bool) -> float:
        best_price = float(0)

        order_book = self.order_books.get(trading_pair)

        if order_book is not None:
            best_price = order_book.get_price(is_buy)

        amm_pool_price, amm_pool_last_tx_timestamp = await self.get_price_from_amm_pool(trading_pair)

        if not math.isnan(amm_pool_price):
            if is_buy:
                best_price = min(best_price, amm_pool_price) if not math.isnan(best_price) else amm_pool_price
            else:
                best_price = max(best_price, amm_pool_price) if not math.isnan(best_price) else amm_pool_price
        return best_price

    async def get_price_from_amm_pool(self, trading_pair: str) -> Tuple[float, int]:
        base_token, quote_token = self.get_currencies_from_trading_pair(trading_pair)
        tx_timestamp = 0
        price = float(0)

        try:
            resp: Response = await self._query_xrpl(
                AMMInfo(
                    asset=base_token,
                    asset2=quote_token,
                ),
                priority=RequestPriority.LOW,
            )
        except Exception as e:
            self.logger().error(f"Error fetching AMM pool info for {trading_pair}: {e}")
            return price, tx_timestamp

        amm_pool_info = resp.result.get("amm", None)

        if amm_pool_info is None:
            return price, tx_timestamp

        try:
            tx_resp: Response = await self._query_xrpl(
                AccountTx(
                    account=resp.result.get("amm", {}).get("account"),
                    limit=1,
                ),
                priority=RequestPriority.LOW,
            )

            tx = tx_resp.result.get("transactions", [{}])[0]
            tx_timestamp = ripple_time_to_posix(tx.get("tx_json", {}).get("date", 0))
        except Exception as e:
            self.logger().error(f"Error fetching AMM pool transaction info for {trading_pair}: {e}")
            return price, tx_timestamp

        amount = amm_pool_info.get("amount")  # type: ignore
        amount2 = amm_pool_info.get("amount2")  # type: ignore

        # Check if we have valid amounts
        if amount is None or amount2 is None:
            return price, tx_timestamp
        if isinstance(amount, str):
            base_amount = drops_to_xrp(amount)
        else:
            base_amount = Decimal(amount.get("value", "0"))

        # Convert quote amount (amount2) if it's XRP
        if isinstance(amount2, str):
            quote_amount = drops_to_xrp(amount2)
        else:
            # For issued currencies, amount2 is a dictionary with a 'value' field
            quote_amount = Decimal(amount2.get("value", "0"))

        # Calculate price as quote/base
        if base_amount == 0:
            return price, tx_timestamp

        price = float(quote_amount / base_amount)

        self.logger().debug(f"AMM pool price for {trading_pair}: {price}")
        self.logger().debug(f"AMM pool transaction timestamp for {trading_pair}: {tx_timestamp}")
        return price, tx_timestamp

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        random_uuid = str(uuid.uuid4())[:6]
        prefix = f"{self.client_order_id_prefix}-{self._nonce_creator.get_tracking_nonce()}-{random_uuid}-"
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=prefix,
            max_id_len=self.client_order_id_max_length,
        )

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        random_uuid = str(uuid.uuid4())[:6]
        prefix = f"{self.client_order_id_prefix}-{self._nonce_creator.get_tracking_nonce()}-{random_uuid}-"
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=prefix,
            max_id_len=self.client_order_id_max_length,
        )
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    async def _update_trading_rules(self):
        trading_rules_info = await self._make_trading_rules_request()
        trading_rules_list = self._format_trading_rules(trading_rules_info)
        trading_pair_fee_rules = self._format_trading_pair_fee_rules(trading_rules_info)
        self._trading_rules.clear()
        self._trading_pair_fee_rules.clear()

        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        for trading_pair_fee_rule in trading_pair_fee_rules:
            self._trading_pair_fee_rules[trading_pair_fee_rule["trading_pair"]] = trading_pair_fee_rule

        exchange_info = self._make_xrpl_trading_pairs_request()

        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = self._make_xrpl_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception(f"There was an error requesting exchange info: {e}")

    async def _make_network_check_request(self):
        await self._node_pool._check_all_connections()

    async def _make_trading_rules_request(self) -> Dict[str, Any]:
        """
        Fetch trading rules from XRPL with retry logic.

        This wrapper adds retry with exponential backoff to handle transient
        connection failures during startup or network instability.
        """
        max_retries = 3
        retry_delay = 2.0  # Initial delay in seconds

        for attempt in range(max_retries):
            try:
                return await self._make_trading_rules_request_impl()
            except Exception as e:
                is_last_attempt = attempt >= max_retries - 1
                if is_last_attempt:
                    self.logger().error(
                        f"Trading rules request failed after {max_retries} attempts: {e}"
                    )
                    raise
                else:
                    self.logger().warning(
                        f"Trading rules request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay:.1f}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

        # Should not reach here, but satisfy type checker
        return {}

    async def _make_trading_rules_request_impl(self) -> Dict[str, Any]:
        """
        Implementation of trading rules request.

        Fetches tick sizes, transfer rates, and AMM pool info for each trading pair.
        """
        zeroTransferRate = 1000000000
        trading_rules_info = {}

        if self._trading_pairs is None:
            raise ValueError("Trading pairs list cannot be None")

        for trading_pair in self._trading_pairs:
            base_currency, quote_currency = self.get_currencies_from_trading_pair(trading_pair)

            if base_currency.currency == XRP().currency:
                baseTickSize = 6  # XRP has 6 decimal places
                baseTransferRate = 0  # XRP has no transfer fee
            else:
                # Ensure base_currency is IssuedCurrency before accessing issuer
                if not isinstance(base_currency, IssuedCurrency):
                    raise ValueError(f"Expected IssuedCurrency but got {type(base_currency)}")

                base_info = await self._query_xrpl(
                    AccountInfo(account=base_currency.issuer, ledger_index="validated"),
                    priority=RequestPriority.LOW,
                )

                if base_info.status == ResponseStatus.ERROR:
                    error_message = base_info.result.get("error_message")
                    raise ValueError(f"Base currency {base_currency} not found in ledger: {error_message}")

                baseTickSize = base_info.result.get("account_data", {}).get("TickSize", 15)
                rawTransferRate = base_info.result.get("account_data", {}).get("TransferRate", zeroTransferRate)
                baseTransferRate = float(rawTransferRate / zeroTransferRate) - 1

            if quote_currency.currency == XRP().currency:
                quoteTickSize = 6  # XRP has 6 decimal places
                quoteTransferRate = 0  # XRP has no transfer fee
            else:
                # Ensure quote_currency is IssuedCurrency before accessing issuer
                if not isinstance(quote_currency, IssuedCurrency):
                    raise ValueError(f"Expected IssuedCurrency but got {type(quote_currency)}")

                quote_info = await self._query_xrpl(
                    AccountInfo(account=quote_currency.issuer, ledger_index="validated"),
                    priority=RequestPriority.LOW,
                )

                if quote_info.status == ResponseStatus.ERROR:
                    error_message = quote_info.result.get("error_message")
                    raise ValueError(f"Quote currency {quote_currency} not found in ledger: {error_message}")

                quoteTickSize = quote_info.result.get("account_data", {}).get("TickSize", 15)
                rawTransferRate = quote_info.result.get("account_data", {}).get("TransferRate", zeroTransferRate)
                quoteTransferRate = float(rawTransferRate / zeroTransferRate) - 1

            smallestTickSize = min(baseTickSize, quoteTickSize)
            minimumOrderSize = float(10) ** -smallestTickSize

            # Get fee from AMM Pool if available
            amm_pool_info = await self.amm_get_pool_info(trading_pair=trading_pair)

            trading_rules_info[trading_pair] = {
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "base_tick_size": baseTickSize,
                "quote_tick_size": quoteTickSize,
                "base_transfer_rate": baseTransferRate,
                "quote_transfer_rate": quoteTransferRate,
                "minimum_order_size": minimumOrderSize,
                "amm_pool_info": amm_pool_info,
            }

        return trading_rules_info

    def _make_xrpl_trading_pairs_request(self) -> Dict[str, XRPLMarket]:
        # Load default markets
        markets = CONSTANTS.MARKETS
        loaded_markets: Dict[str, XRPLMarket] = {}

        # Load each market into XRPLMarket
        for k, v in markets.items():
            loaded_markets[k] = XRPLMarket(
                base=v["base"],
                base_issuer=v["base_issuer"],
                quote=v["quote"],
                quote_issuer=v["quote_issuer"],
                trading_pair_symbol=k,
            )

        # Merge default markets with custom markets
        loaded_markets.update(self._custom_markets)

        return loaded_markets

    def get_currencies_from_trading_pair(
        self, trading_pair: str
    ) -> (Tuple)[Union[IssuedCurrency, XRP], Union[IssuedCurrency, XRP]]:
        # Find market in the markets list
        all_markets = self._make_xrpl_trading_pairs_request()
        market = all_markets.get(trading_pair, None)

        if market is None:
            raise ValueError(f"Market {trading_pair} not found in markets list")

        # Get all info
        base = market.base
        base_issuer = market.base_issuer
        quote = market.quote
        quote_issuer = market.quote_issuer

        if base == "XRP":
            base_currency = XRP()
        else:
            formatted_base = convert_string_to_hex(base)
            base_currency = IssuedCurrency(currency=formatted_base, issuer=base_issuer)

        if quote == "XRP":
            quote_currency = XRP()
        else:
            formatted_quote = convert_string_to_hex(quote)
            quote_currency = IssuedCurrency(currency=formatted_quote, issuer=quote_issuer)

        return base_currency, quote_currency

    async def tx_autofill(
        self, transaction: Transaction, client: Client, signers_count: Optional[int] = None
    ) -> Transaction:
        return await autofill(transaction, client, signers_count)

    def tx_sign(
        self,
        transaction: Transaction,
        wallet: Wallet,
        multisign: bool = False,
    ) -> Transaction:
        return sign(transaction, wallet, multisign)

    async def tx_submit(
        self,
        transaction: Transaction,
        client: Client,
        *,
        fail_hard: bool = False,
    ) -> Response:
        transaction_blob = encode(transaction.to_xrpl())
        response = await client._request_impl(
            SubmitOnly(tx_blob=transaction_blob, fail_hard=fail_hard), timeout=CONSTANTS.REQUEST_TIMEOUT
        )
        if response.is_successful():
            return response

        raise XRPLRequestFailureException(response.result)

    async def wait_for_final_transaction_outcome(self, transaction, prelim_result, max_attempts: int = 10) -> Response:
        """
        Wait for a transaction to be finalized on the XRPL ledger using the worker pool.

        This method polls the ledger until:
        1. The transaction is found in a validated ledger (success)
        2. The transaction's LastLedgerSequence has been passed (failure)
        3. Max attempts reached (timeout)

        Args:
            transaction: The signed transaction to verify
            prelim_result: The preliminary result from submission
            max_attempts: Maximum number of polling attempts (default 30, ~30 seconds)

        Returns:
            Response containing the validated transaction

        Raises:
            XRPLReliableSubmissionException: If transaction failed or ledger sequence exceeded
            TimeoutError: If max attempts reached without finalization
        """
        tx_hash = transaction.get_hash()
        last_ledger_sequence = transaction.last_ledger_sequence

        # DEBUG LOG - DELETE LATER
        self.logger().debug(
            f"[DEBUG_WAIT] wait_for_final_transaction_outcome START: tx_hash={tx_hash[:16]}..., "
            f"last_ledger_sequence={last_ledger_sequence}, max_attempts={max_attempts}"
        )

        for attempt in range(max_attempts):
            # Wait before checking (ledger closes every ~3-4 seconds)
            await asyncio.sleep(1)

            try:
                # Get current ledger sequence to check if we've passed the deadline
                ledger_request = Ledger(ledger_index="validated")
                ledger_response = await self._query_xrpl(ledger_request)

                if ledger_response.is_successful():
                    current_ledger_sequence = ledger_response.result.get("ledger_index", 0)

                    # DEBUG LOG - DELETE LATER
                    self.logger().debug(
                        f"[DEBUG_WAIT] Ledger check: tx_hash={tx_hash[:16]}..., "
                        f"current_ledger={current_ledger_sequence}, last_ledger={last_ledger_sequence}, "
                        f"attempt={attempt + 1}/{max_attempts}"
                    )

                    # Check if we've exceeded the last ledger sequence by too much
                    if (
                        current_ledger_sequence >= last_ledger_sequence
                        and (current_ledger_sequence - last_ledger_sequence) > 10
                    ):
                        raise XRPLReliableSubmissionException(
                            f"Transaction failed - latest ledger {current_ledger_sequence} exceeds "
                            f"transaction's LastLedgerSequence {last_ledger_sequence}. "
                            f"Prelim result: {prelim_result}"
                        )
                else:
                    # DEBUG LOG - DELETE LATER
                    self.logger().debug(
                        f"[DEBUG_WAIT] Ledger request failed: tx_hash={tx_hash[:16]}..., "
                        f"response={ledger_response.result}"
                    )

                # Query transaction by hash
                tx_request = Tx(transaction=tx_hash)
                tx_response = await self._query_xrpl(tx_request)

                if not tx_response.is_successful():
                    error = tx_response.result.get("error", "unknown")
                    if error == "txnNotFound":
                        # Transaction not yet in a validated ledger, keep polling
                        self.logger().debug(
                            f"Transaction {tx_hash[:16]}... not found yet, attempt {attempt + 1}/{max_attempts}"
                        )
                        continue
                    else:
                        # Other error - log and continue polling
                        self.logger().warning(
                            f"Error querying transaction {tx_hash[:16]}...: {error}, attempt {attempt + 1}/{max_attempts}"
                        )
                        continue

                result = tx_response.result
                if result.get("validated", False):
                    # DEBUG LOG - DELETE LATER
                    return_code = result.get("meta", {}).get("TransactionResult", "unknown")
                    self.logger().debug(
                        f"[DEBUG_WAIT] Transaction validated: tx_hash={tx_hash[:16]}..., " f"return_code={return_code}"
                    )

                    # Transaction is in a validated ledger - outcome is final
                    if return_code != "tesSUCCESS":
                        raise XRPLReliableSubmissionException(f"Transaction failed: {return_code}")
                    return tx_response

                # Transaction found but not yet validated, continue polling
                self.logger().debug(
                    f"Transaction {tx_hash[:16]}... found but not validated yet, attempt {attempt + 1}/{max_attempts}"
                )

            except XRPLReliableSubmissionException:
                # Re-raise submission exceptions
                raise
            except Exception as e:
                # DEBUG LOG - DELETE LATER
                self.logger().debug(
                    f"[DEBUG_WAIT] Exception in polling loop: tx_hash={tx_hash[:16]}..., "
                    f"error_type={type(e).__name__}, error={e}, attempt={attempt + 1}/{max_attempts}"
                )
                # Log error but continue polling - connection issues shouldn't stop verification
                continue

        # DEBUG LOG - DELETE LATER
        self.logger().debug(f"[DEBUG_WAIT] Max attempts reached: tx_hash={tx_hash[:16]}..., max_attempts={max_attempts}")

        # Max attempts reached
        raise TimeoutError(
            f"Transaction verification timed out after {max_attempts} attempts. "
            f"tx_hash={tx_hash}, prelim_result={prelim_result}"
        )

    def get_token_symbol_from_all_markets(self, code: str, issuer: str) -> Optional[str]:
        all_markets = self._make_xrpl_trading_pairs_request()
        for market_name, market in all_markets.items():
            token_symbol = market.get_token_symbol(code, issuer)

            if token_symbol is not None:
                # DEBUG LOG - DELETE LATER
                self.logger().debug(
                    f"[DEBUG_TOKEN_SYMBOL] MATCH: code={code}, issuer={issuer}, "
                    f"market={market_name}, resolved_symbol={token_symbol.upper()}"
                )
                return token_symbol.upper()

        # DEBUG LOG - DELETE LATER
        self.logger().debug(
            f"[DEBUG_TOKEN_SYMBOL] NO MATCH: code={code}, issuer={issuer}, "
            f"searched {len(all_markets)} markets"
        )
        return None

    # AMM functions
    async def amm_get_pool_info(
        self, pool_address: Optional[str] = None, trading_pair: Optional[str] = None
    ) -> Optional[PoolInfo]:
        """
        Get information about a specific AMM liquidity pool

        :param pool_address: The address of the AMM pool
        :param trading_pair: The trading pair to get the pool info for
        :param network: Optional network specification
        :return: Pool information
        """
        if pool_address is not None:
            resp: Response = await self._query_xrpl(
                AMMInfo(amm_account=pool_address),
                priority=RequestPriority.LOW,
            )
        elif trading_pair is not None:
            base_token, quote_token = self.get_currencies_from_trading_pair(trading_pair)
            resp: Response = await self._query_xrpl(
                AMMInfo(
                    asset=base_token,
                    asset2=quote_token,
                ),
                priority=RequestPriority.LOW,
            )
        else:
            self.logger().error("No pool_address or trading_pair provided")
            return None

        # Process the response and convert to our PoolInfo model
        amm_pool_info = resp.result.get("amm", {})

        # Extract pool address
        extracted_pool_address = amm_pool_info.get("account", None)

        if extracted_pool_address is None:
            self.logger().debug(f"No AMM pool info found for {trading_pair if trading_pair else pool_address}")
            return None

        # Extract amounts
        amount1: Any = amm_pool_info.get("amount", None)
        amount2: Any = amm_pool_info.get("amount2", None)
        lp_token: Any = amm_pool_info.get("lp_token", None)

        if amount1 is None or amount2 is None or lp_token is None:
            self.logger().error(f"Missing amounts or lp_token for {trading_pair if trading_pair else pool_address}")
            return None

        # Convert to decimals based on token type
        if isinstance(amount1, str):
            base_amount = drops_to_xrp(amount1)
        else:
            base_amount = Decimal(amount1.get("value", "0"))

        if isinstance(amount2, str):
            quote_amount = drops_to_xrp(amount2)
        else:
            quote_amount = Decimal(amount2.get("value", "0"))

        lp_token_amount = Decimal(lp_token.get("value", "0")) if lp_token else Decimal("0")

        # Calculate price
        price = quote_amount / base_amount if base_amount > 0 else Decimal("0")

        # Get fee percentage
        fee_pct = Decimal(amm_pool_info.get("trading_fee", "0")) / Decimal(
            "1000"
        )  # XRPL expresses fees in basis points

        base_token_address: Currency = (
            IssuedCurrency(currency=amount1.get("currency"), issuer=amount1.get("issuer"))
            if not isinstance(amount1, str)
            else XRP()
        )
        quote_token_address: Currency = (
            IssuedCurrency(currency=amount2.get("currency"), issuer=amount2.get("issuer"))
            if not isinstance(amount2, str)
            else XRP()
        )
        lp_token_addess: Currency = IssuedCurrency(currency=lp_token.get("currency"), issuer=lp_token.get("issuer"))

        return PoolInfo(
            address=extracted_pool_address,
            base_token_address=base_token_address,
            quote_token_address=quote_token_address,
            lp_token_address=lp_token_addess,
            fee_pct=fee_pct,
            price=price,
            base_token_amount=base_amount,
            quote_token_amount=quote_amount,
            lp_token_amount=lp_token_amount,
            pool_type="XRPL-AMM",
        )

    async def amm_quote_add_liquidity(
        self,
        pool_address: str,
        base_token_amount: Decimal,
        quote_token_amount: Decimal,
        slippage_pct: Decimal = Decimal("0"),
        network: Optional[str] = None,
    ) -> Optional[QuoteLiquidityResponse]:
        """
        Get a quote for adding liquidity to an AMM pool

        :param pool_address: The address of the AMM pool
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Optional slippage percentage
        :param network: Optional network specification
        :return: Quote for adding liquidity
        """
        # Get current pool state
        pool_info = await self.amm_get_pool_info(pool_address, network)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return None

        # Calculate the optimal amounts based on current pool ratio
        current_ratio = (
            pool_info.quote_token_amount / pool_info.base_token_amount
            if pool_info.base_token_amount > 0
            else Decimal("0")
        )

        # Calculate maximum amounts based on provided amounts
        if base_token_amount * current_ratio > quote_token_amount:
            # Base limited
            base_limited = True
            quote_token_amount_required = base_token_amount * current_ratio
            quote_token_amount_max = quote_token_amount_required * (Decimal("1") + (slippage_pct))
            return QuoteLiquidityResponse(
                base_limited=base_limited,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount_required,
                base_token_amount_max=base_token_amount,
                quote_token_amount_max=quote_token_amount_max,
            )
        else:
            # Quote limited
            base_limited = False
            base_token_amount_required = quote_token_amount / current_ratio
            base_token_amount_max = base_token_amount_required * (Decimal("1") + (slippage_pct))
            return QuoteLiquidityResponse(
                base_limited=base_limited,
                base_token_amount=base_token_amount_required,
                quote_token_amount=quote_token_amount,
                base_token_amount_max=base_token_amount_max,
                quote_token_amount_max=quote_token_amount,
            )

    async def amm_add_liquidity(
        self,
        pool_address: str,
        wallet_address: str,
        base_token_amount: Decimal,
        quote_token_amount: Decimal,
        slippage_pct: Decimal = Decimal("0"),
        network: Optional[str] = None,
    ) -> Optional[AddLiquidityResponse]:
        """
        Add liquidity to an AMM pool

        :param pool_address: The address of the AMM pool
        :param wallet_address: The address of the wallet to use
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Optional slippage percentage
        :param network: Optional network specification
        :return: Result of adding liquidity
        """
        # Get pool info to determine token types
        pool_info = await self.amm_get_pool_info(pool_address, network)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return None

        # Get quote to determine optimal amounts
        quote = await self.amm_quote_add_liquidity(
            pool_address=pool_address,
            base_token_amount=base_token_amount,
            quote_token_amount=quote_token_amount,
            slippage_pct=slippage_pct,
            network=network,
        )

        if quote is None:
            self.logger().error(f"No quote found for {pool_address}")
            return None

        # Convert amounts based on token types (XRP vs. issued token)
        if isinstance(pool_info.base_token_address, XRP):
            base_amount = xrp_to_drops(quote.base_token_amount)
        else:
            base_value_amount = str(Decimal(quote.base_token_amount).quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
            base_amount = IssuedCurrencyAmount(
                currency=pool_info.base_token_address.currency,
                issuer=pool_info.base_token_address.issuer,
                value=base_value_amount,
            )

        if isinstance(pool_info.quote_token_address, XRP):
            quote_amount = xrp_to_drops(quote.quote_token_amount)
        else:
            quote_value_amount = str(
                Decimal(quote.quote_token_amount).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
            )
            quote_amount = IssuedCurrencyAmount(
                currency=pool_info.quote_token_address.currency,
                issuer=pool_info.quote_token_address.issuer,
                value=quote_value_amount,
            )

        # Create memo
        memo_text = f"HBOT-Add-Liquidity:{pool_address}:{base_token_amount:.5f}({pool_info.base_token_address.currency}):{quote_token_amount:.5f}({pool_info.quote_token_address.currency})"
        memo = Memo(
            memo_data=convert_string_to_hex(memo_text, padding=False),
        )

        # Create AMMDeposit transaction
        account = self._xrpl_auth.get_account()
        deposit_transaction = AMMDeposit(
            account=account,
            asset=pool_info.base_token_address,
            asset2=pool_info.quote_token_address,
            amount=base_amount,
            amount2=quote_amount,
            lp_token_out=None,
            flags=1048576,
            memos=[memo],
        )

        # Sign and submit transaction via worker manager
        submit_result = await self._submit_transaction(deposit_transaction)
        tx_response = submit_result["response"]

        # Get balance changes
        tx_metadata = tx_response.result.get("meta", {})
        balance_changes = get_balance_changes(tx_metadata)

        base_token_amount_added = Decimal("0")
        quote_token_amount_added = Decimal("0")

        # Find balance changes by wallet address
        for change in balance_changes:
            if change.get("account") == wallet_address:
                # Check if the change is for the LP token
                balances = change.get("balances", [])
                for balance in balances:
                    if balance.get("currency") == pool_info.base_token_address.currency:
                        # Extract the base token amount removed
                        base_token_amount_added = abs(Decimal(balance.get("value")))
                    elif balance.get("currency") == pool_info.quote_token_address.currency:
                        # Extract the quote token amount removed
                        quote_token_amount_added = abs(Decimal(balance.get("value")))

        # Extract fee
        fee = drops_to_xrp(tx_response.result.get("tx_json", {}).get("Fee", "0"))

        return AddLiquidityResponse(
            signature=tx_response.result.get("tx_json", {}).get("hash", ""),
            fee=fee,
            base_token_amount_added=base_token_amount_added,
            quote_token_amount_added=quote_token_amount_added,
        )

    async def amm_remove_liquidity(
        self, pool_address: str, wallet_address: str, percentage_to_remove: Decimal, network: Optional[str] = None
    ) -> Optional[RemoveLiquidityResponse]:
        """
        Remove liquidity from an AMM pool

        :param pool_address: The address of the AMM pool
        :param wallet_address: The address of the wallet to use
        :param percentage_to_remove: Percentage of liquidity to remove (0-100)
        :param network: Optional network specification
        :return: Result of removing liquidity
        """
        # Get current pool info
        pool_info = await self.amm_get_pool_info(pool_address, network)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return None

        # Get user's LP tokens for this pool
        account = self._xrpl_auth.get_account()
        resp = await self._query_xrpl(
            AccountObjects(account=account),
            priority=RequestPriority.LOW,
        )

        account_objects = resp.result.get("account_objects", [])

        # Filter for currency that matches lp token issuer
        lp_tokens = [
            obj for obj in account_objects if obj.get("Balance").get("currency") == pool_info.lp_token_address.currency
        ]

        lp_token_amount = lp_tokens.pop(0).get("Balance").get("value")

        if not lp_token_amount:
            raise ValueError(f"No LP tokens found for pool {pool_address}")
        #
        # Calculate amount to withdraw based on percentage
        withdraw_amount = abs(Decimal(lp_token_amount) * (percentage_to_remove / Decimal("100"))).quantize(
            Decimal("0.000001"), rounding=ROUND_DOWN
        )

        if percentage_to_remove >= Decimal("100"):
            withdraw_flag = 0x00020000
            lp_token_to_withdraw = None
        else:
            withdraw_flag = 0x00010000
            lp_token_to_withdraw = IssuedCurrencyAmount(
                currency=pool_info.lp_token_address.currency,
                issuer=pool_info.lp_token_address.issuer,
                value=str(withdraw_amount),
            )

        # Create memo
        memo_text = f"HBOT-Remove-Liquidity:{pool_address}:{percentage_to_remove}"
        memo = Memo(
            memo_data=convert_string_to_hex(memo_text, padding=False),
        )

        # Create AMMWithdraw transaction
        withdraw_transaction = AMMWithdraw(
            account=wallet_address,
            asset=pool_info.base_token_address,
            asset2=pool_info.quote_token_address,
            lp_token_in=lp_token_to_withdraw,
            flags=withdraw_flag,
            memos=[memo],
        )

        self.logger().debug(f"AMMWithdraw transaction: {withdraw_transaction}")

        # Sign and submit transaction via worker manager
        submit_result = await self._submit_transaction(withdraw_transaction)
        tx_response = submit_result["response"]
        tx_metadata = tx_response.result.get("meta", {})
        balance_changes = get_balance_changes(tx_metadata)

        base_token_amount_removed = Decimal("0")
        quote_token_amount_removed = Decimal("0")

        # Find balance changes by wallet address
        for change in balance_changes:
            if change.get("account") == wallet_address:
                # Check if the change is for the LP token
                balances = change.get("balances", [])
                for balance in balances:
                    if balance.get("currency") == pool_info.base_token_address.currency:
                        # Extract the base token amount removed
                        base_token_amount_removed = Decimal(balance.get("value", "0"))
                    elif balance.get("currency") == pool_info.quote_token_address.currency:
                        # Extract the quote token amount removed
                        quote_token_amount_removed = Decimal(balance.get("value", "0"))

        # Extract fee
        fee = drops_to_xrp(tx_response.result.get("tx_json", {}).get("Fee", "0"))

        return RemoveLiquidityResponse(
            signature=tx_response.result.get("tx_json", {}).get("hash", ""),
            fee=fee,
            base_token_amount_removed=base_token_amount_removed,
            quote_token_amount_removed=quote_token_amount_removed,
        )

    async def amm_get_balance(self, pool_address: str, wallet_address: str) -> Dict[str, Any]:
        """
        Get the balance of an AMM pool for a specific wallet address

        :param pool_address: The address of the AMM pool
        :param wallet_address: The address of the wallet to check
        :return: A dictionary containing the balance information
        """
        # Use the XRPL AccountLines query
        resp: Response = await self._query_xrpl(
            AccountLines(
                account=wallet_address,
                peer=pool_address,
            ),
            priority=RequestPriority.LOW,
        )

        # Process the response and extract balance information
        lines = resp.result.get("lines", [])

        # Get AMM Pool info
        pool_info: PoolInfo | None = await self.amm_get_pool_info(pool_address)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return {
                "base_token_lp_amount": Decimal("0"),
                "base_token_address": None,
                "quote_token_lp_amount": Decimal("0"),
                "quote_token_address": None,
                "lp_token_amount": Decimal("0"),
                "lp_token_amount_pct": Decimal("0"),
            }

        lp_token_balance = None
        for line in lines:
            if line.get("account") == pool_address:
                lp_token_balance = {
                    "balance": line.get("balance"),
                    "currency": line.get("currency"),
                    "issuer": line.get("account"),
                }
                break

        if lp_token_balance is None:
            return {
                "base_token_lp_amount": Decimal("0"),
                "base_token_address": pool_info.base_token_address,
                "quote_token_lp_amount": Decimal("0"),
                "quote_token_address": pool_info.quote_token_address,
                "lp_token_amount": Decimal("0"),
                "lp_token_amount_pct": Decimal("0"),
            }

        lp_token_amount = Decimal(lp_token_balance.get("balance", "0"))
        lp_token_amount_pct = (
            lp_token_amount / pool_info.lp_token_amount if pool_info.lp_token_amount > 0 else Decimal("0")
        )
        base_token_lp_amount = pool_info.base_token_amount * lp_token_amount_pct
        quote_token_lp_amount = pool_info.quote_token_amount * lp_token_amount_pct

        balance_info = {
            "base_token_lp_amount": base_token_lp_amount,
            "base_token_address": pool_info.base_token_address,
            "quote_token_lp_amount": quote_token_lp_amount,
            "quote_token_address": pool_info.quote_token_address,
            "lp_token_amount": lp_token_amount,
            "lp_token_amount_pct": lp_token_amount_pct * Decimal("100"),
        }

        return balance_info
