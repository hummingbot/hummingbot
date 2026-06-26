"""
XRPL Worker Pool Module

This module provides concurrent worker pools for XRPL operations:
- XRPLQueryWorkerPool: Concurrent read-only queries
- XRPLVerificationWorkerPool: Concurrent transaction verification
- XRPLTransactionWorkerPool: Concurrent preparation, serialized submission via pipeline

Architecture:
- Each pool manages multiple worker coroutines
- Workers acquire clients from the node pool per task (round-robin)
- Clients are released back to the pool after task completion
- Transaction submissions are serialized through a shared pipeline to prevent sequence conflicts

Error Handling:
- On client error: try reconnect same client
- If reconnect fails: get new healthy client from pool
- If no healthy client available: wait with timeout
- If timeout expires: fail the task with error
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, TypeVar

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.asyncio.clients.exceptions import XRPLWebsocketException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException, sign
from xrpl.core.binarycodec import encode
from xrpl.models import Request, Response, SubmitOnly, Transaction, Tx
from xrpl.wallet import Wallet

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    XRPLConnectionError,
    XRPLNodePool,
    XRPLTimeoutError,
    _wait_for_final_transaction_outcome,
    autofill,
)
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_transaction_pipeline import XRPLTransactionPipeline


# Type variable for generic pool result type
T = TypeVar("T")


# ============================================
# Result Dataclasses
# ============================================

@dataclass
class TransactionSubmitResult:
    """Result of a transaction submission."""
    success: bool
    signed_tx: Optional[Transaction] = None
    response: Optional[Response] = None
    prelim_result: Optional[str] = None
    exchange_order_id: Optional[str] = None
    error: Optional[str] = None
    tx_hash: Optional[str] = None

    @property
    def is_queued(self) -> bool:
        """Check if transaction was queued (terQUEUED)."""
        return self.prelim_result == "terQUEUED"

    @property
    def is_accepted(self) -> bool:
        """Check if transaction was accepted (tesSUCCESS or terQUEUED)."""
        return self.prelim_result in ("tesSUCCESS", "terQUEUED")


@dataclass
class TransactionVerifyResult:
    """Result of a transaction verification."""
    verified: bool
    response: Optional[Response] = None
    final_result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class QueryResult:
    """Result of a query operation."""
    success: bool
    response: Optional[Response] = None
    error: Optional[str] = None


# ============================================
# Worker Task Dataclass
# ============================================

@dataclass
class WorkerTask(Generic[T]):
    """Represents a task submitted to a worker pool."""
    task_id: str
    request: Any
    future: asyncio.Future
    created_at: float = field(default_factory=time.time)
    timeout: float = CONSTANTS.WORKER_TASK_TIMEOUT
    max_queue_time: float = CONSTANTS.WORKER_MAX_QUEUE_TIME

    @property
    def is_expired(self) -> bool:
        """Check if the task has waited too long in the queue.

        Note: This only checks queue wait time, not processing time.
        Processing timeout is handled separately in the worker loop.
        """
        return (time.time() - self.created_at) > self.max_queue_time


# ============================================
# Pool Statistics
# ============================================

@dataclass
class PoolStats:
    """Statistics for a worker pool."""
    pool_name: str
    num_workers: int
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_pending: int = 0
    total_latency_ms: float = 0.0
    client_reconnects: int = 0
    client_failures: int = 0

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average task latency."""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 0.0
        return self.total_latency_ms / total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        return {
            "pool_name": self.pool_name,
            "num_workers": self.num_workers,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_pending": self.tasks_pending,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "client_reconnects": self.client_reconnects,
            "client_failures": self.client_failures,
        }


# ============================================
# Base Worker Pool Class
# ============================================

class XRPLWorkerPoolBase(ABC, Generic[T]):
    """
    Abstract base class for XRPL worker pools.

    Features:
    - Multiple concurrent worker coroutines
    - Task queue management
    - Round-robin client acquisition per task
    - Error handling with reconnect/retry logic
    - Statistics tracking

    Subclasses must implement:
    - _process_task(): Execute the actual work for a task
    """
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        node_pool: XRPLNodePool,
        pool_name: str,
        num_workers: int,
        max_queue_size: int = CONSTANTS.WORKER_POOL_TASK_QUEUE_SIZE,
    ):
        """
        Initialize the worker pool.

        Args:
            node_pool: The XRPL node pool for getting connections
            pool_name: Name of the pool for logging
            num_workers: Number of concurrent worker coroutines
            max_queue_size: Maximum pending tasks in the queue
        """
        self._node_pool = node_pool
        self._pool_name = pool_name
        self._num_workers = num_workers
        self._max_queue_size = max_queue_size

        # Task queue
        self._task_queue: asyncio.Queue[WorkerTask] = asyncio.Queue(maxsize=max_queue_size)

        # Worker tasks
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
        self._started = False  # Track if pool was ever started (for lazy init)

        # Statistics
        self._stats = PoolStats(pool_name=pool_name, num_workers=num_workers)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    def is_running(self) -> bool:
        """Check if the pool is running."""
        return self._running

    @property
    def stats(self) -> PoolStats:
        """Get pool statistics."""
        self._stats.tasks_pending = self._task_queue.qsize()
        return self._stats

    async def start(self):
        """Start the worker pool."""
        if self._running:
            self.logger().warning(f"[{self._pool_name}] Pool is already running")
            return

        self._running = True
        self._started = True

        # Create worker tasks
        for i in range(self._num_workers):
            worker_task = asyncio.create_task(self._worker_loop(worker_id=i))
            self._worker_tasks.append(worker_task)

        self.logger().debug(
            f"[{self._pool_name}] Started pool with {self._num_workers} workers"
        )

    async def stop(self):
        """Stop the worker pool and cancel pending tasks."""
        if not self._running:
            return

        self._running = False
        self.logger().debug(f"[{self._pool_name}] Stopping pool...")

        # Cancel all worker tasks
        for worker_task in self._worker_tasks:
            worker_task.cancel()

        # Wait for workers to finish
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

        # Cancel pending tasks in queue
        cancelled_count = 0
        while not self._task_queue.empty():
            try:
                task = self._task_queue.get_nowait()
                if not task.future.done():
                    task.future.cancel()
                    cancelled_count += 1
            except asyncio.QueueEmpty:
                break

        self.logger().debug(
            f"[{self._pool_name}] Pool stopped, cancelled {cancelled_count} pending tasks"
        )

    async def _ensure_started(self):
        """Ensure the pool is started (lazy initialization)."""
        if not self._started:
            await self.start()

    async def submit(self, request: Any, timeout: Optional[float] = None) -> T:
        """
        Submit a task to the worker pool.

        Args:
            request: The request to process
            timeout: Optional timeout override

        Returns:
            The result of processing the task

        Raises:
            asyncio.QueueFull: If the task queue is full
            Exception: Any exception from task processing
        """
        # Lazy start
        await self._ensure_started()

        task_id = str(uuid.uuid4())[:8]
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        task = WorkerTask(
            task_id=task_id,
            request=request,
            future=future,
            timeout=timeout or CONSTANTS.WORKER_TASK_TIMEOUT,
        )

        try:
            self._task_queue.put_nowait(task)
            self.logger().debug(
                f"[{self._pool_name}] Task {task_id} queued "
                f"(queue_size={self._task_queue.qsize()}, request_type={type(request).__name__})"
            )
        except asyncio.QueueFull:
            self.logger().error(
                f"[{self._pool_name}] Task queue full, rejecting task {task_id}"
            )
            raise

        # Wait for result - no timeout here since queue wait time should not count
        # The processing timeout is applied in the worker loop when the task is picked up
        try:
            result = await future
            return result
        except asyncio.CancelledError:
            self.logger().warning(f"[{self._pool_name}] Task {task_id} was cancelled")
            raise
        except asyncio.TimeoutError:
            # This timeout comes from the worker loop during processing
            self.logger().error(f"[{self._pool_name}] Task {task_id} timed out during processing")
            raise

    async def _worker_loop(self, worker_id: int):
        """
        Worker loop that processes tasks from the queue.

        Args:
            worker_id: Identifier for this worker
        """
        self.logger().debug(f"[{self._pool_name}] Worker {worker_id} started and ready")

        while self._running:
            try:
                # Get next task with timeout
                try:
                    task = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Skip expired or cancelled tasks
                if task.future.done():
                    self.logger().debug(
                        f"[{self._pool_name}] Worker {worker_id} skipping cancelled task {task.task_id}"
                    )
                    continue

                if task.is_expired:
                    queue_time = time.time() - task.created_at
                    self.logger().warning(
                        f"[{self._pool_name}] Worker {worker_id} skipping expired task {task.task_id} "
                        f"(waited {queue_time:.1f}s in queue, max={task.max_queue_time}s)"
                    )
                    if not task.future.done():
                        task.future.set_exception(
                            asyncio.TimeoutError(f"Task {task.task_id} expired after {queue_time:.1f}s in queue")
                        )
                    self._stats.tasks_failed += 1
                    continue

                # Process the task with timeout (timeout only applies to processing, not queue wait)
                queue_time = time.time() - task.created_at
                self.logger().debug(
                    f"[{self._pool_name}] Worker {worker_id} processing task {task.task_id} "
                    f"(queued for {queue_time:.1f}s)"
                )
                start_time = time.time()
                try:
                    # Apply timeout only to the actual processing
                    result = await asyncio.wait_for(
                        self._process_task_with_retry(task, worker_id),
                        timeout=task.timeout
                    )
                    elapsed_ms = (time.time() - start_time) * 1000

                    if not task.future.done():
                        task.future.set_result(result)

                    self._stats.tasks_completed += 1
                    self._stats.total_latency_ms += elapsed_ms

                    self.logger().debug(
                        f"[{self._pool_name}] Worker {worker_id} completed task {task.task_id} "
                        f"in {elapsed_ms:.1f}ms (success={getattr(result, 'success', True)})"
                    )

                except asyncio.TimeoutError:
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.logger().error(
                        f"[{self._pool_name}] Worker {worker_id} task {task.task_id} timed out "
                        f"after {elapsed_ms:.1f}ms processing (timeout={task.timeout}s)"
                    )
                    if not task.future.done():
                        task.future.set_exception(
                            asyncio.TimeoutError(
                                f"Task {task.task_id} timed out after {elapsed_ms:.1f}ms processing"
                            )
                        )
                    self._stats.tasks_failed += 1

                except Exception as e:
                    elapsed_ms = (time.time() - start_time) * 1000

                    if not task.future.done():
                        task.future.set_exception(e)

                    self._stats.tasks_failed += 1
                    self._stats.total_latency_ms += elapsed_ms

                    self.logger().error(
                        f"[{self._pool_name}] Worker {worker_id} failed task {task.task_id} "
                        f"after {elapsed_ms:.1f}ms: {e}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger().error(
                    f"[{self._pool_name}] Worker {worker_id} unexpected error: {e}"
                )

        self.logger().debug(f"[{self._pool_name}] Worker {worker_id} stopped")

    async def _process_task_with_retry(self, task: WorkerTask, worker_id: int) -> T:
        """
        Process a task with client error handling and retry.

        Error handling flow:
        1. Get client from pool
        2. Try to process task
        3. On error: try reconnect same client
        4. If reconnect fails: get new healthy client
        5. If no healthy client: wait with timeout
        6. If timeout: raise error

        Args:
            task: The task to process
            worker_id: The worker processing the task

        Returns:
            The result of processing
        """
        client = None
        reconnect_attempts = 0
        max_reconnect = CONSTANTS.WORKER_CLIENT_RECONNECT_ATTEMPTS

        while True:
            try:
                # Get client if we don't have one
                if client is None:
                    client = await self._get_client_with_timeout(worker_id)

                # Process the task
                return await self._process_task(task, client)

            except (XRPLConnectionError, XRPLWebsocketException) as e:
                self.logger().warning(
                    f"[{self._pool_name}] Worker {worker_id} connection error: {e}"
                )

                # Try to reconnect
                if reconnect_attempts < max_reconnect:
                    reconnect_attempts += 1
                    self._stats.client_reconnects += 1

                    self.logger().debug(
                        f"[{self._pool_name}] Worker {worker_id} attempting reconnect "
                        f"({reconnect_attempts}/{max_reconnect})"
                    )

                    try:
                        # Try to reconnect the existing client
                        if client is not None:
                            await client.open()
                            self.logger().debug(
                                f"[{self._pool_name}] Worker {worker_id} reconnected successfully"
                            )
                            continue
                    except Exception as reconnect_error:
                        self.logger().warning(
                            f"[{self._pool_name}] Worker {worker_id} reconnect failed: {reconnect_error}"
                        )

                    # Get a new client
                    client = None
                    continue

                # Max reconnects reached, fail
                self._stats.client_failures += 1
                raise XRPLConnectionError(
                    f"Failed after {max_reconnect} reconnect attempts: {e}"
                )

            except Exception:
                # Non-connection error, don't retry
                raise

    async def _get_client_with_timeout(self, worker_id: int) -> AsyncWebsocketClient:
        """
        Get a healthy client from the node pool with timeout.

        Args:
            worker_id: The worker requesting the client

        Returns:
            A healthy WebSocket client

        Raises:
            XRPLConnectionError: If no client available within timeout
        """
        timeout = CONSTANTS.WORKER_CLIENT_RETRY_TIMEOUT
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            try:
                client = await self._node_pool.get_client(use_burst=False)
                return client
            except Exception as e:
                self.logger().warning(
                    f"[{self._pool_name}] Worker {worker_id} failed to get client: {e}"
                )
                await asyncio.sleep(0.5)

        self._stats.client_failures += 1
        raise XRPLConnectionError(
            f"No healthy client available after {timeout}s timeout"
        )

    @abstractmethod
    async def _process_task(self, task: WorkerTask, client: AsyncWebsocketClient) -> T:
        """
        Process a single task. Must be implemented by subclasses.

        Args:
            task: The task to process
            client: The client to use for the operation

        Returns:
            The result of the task
        """
        pass


# ============================================
# Query Worker Pool
# ============================================

class XRPLQueryWorkerPool(XRPLWorkerPoolBase[QueryResult]):
    """
    Worker pool for concurrent read-only XRPL queries.

    Use for: AccountInfo, AccountTx, AccountObjects, Tx, ServerInfo, etc.
    """

    def __init__(
        self,
        node_pool: XRPLNodePool,
        num_workers: int = CONSTANTS.QUERY_WORKER_POOL_SIZE,
    ):
        super().__init__(
            node_pool=node_pool,
            pool_name="QueryPool",
            num_workers=num_workers,
        )

    async def _process_task(
        self,
        task: WorkerTask,
        client: AsyncWebsocketClient,
    ) -> QueryResult:
        """
        Execute a query against the XRPL.

        Args:
            task: The task containing the request
            client: The client to use

        Returns:
            QueryResult with success status and response
        """
        request: Request = task.request
        request_type = type(request).__name__

        try:
            response = await client._request_impl(request)

            if response.is_successful():
                return QueryResult(success=True, response=response)
            else:
                error = response.result.get("error", "Unknown error")
                error_message = response.result.get("error_message", "")
                full_error = f"{error}: {error_message}" if error_message else error
                self.logger().warning(
                    f"[QueryPool] {request_type} request returned error: {full_error}"
                )
                return QueryResult(success=False, response=response, error=full_error)

        except XRPLConnectionError:
            # Re-raise connection errors for retry handling
            raise
        except KeyError as e:
            # KeyError can occur if the connection reconnects during the request,
            # which clears _open_requests in the XRPL library
            self.logger().warning(f"[QueryPool] Request lost during client reconnection: {e}")
            raise XRPLConnectionError(f"Request lost during reconnection: {e}")
        except Exception as e:
            # Provide more context in error messages
            error_msg = f"{request_type} query failed: {type(e).__name__}: {str(e)}"
            self.logger().error(f"[QueryPool] {error_msg}")
            return QueryResult(success=False, error=error_msg)


# ============================================
# Verification Worker Pool
# ============================================

class XRPLVerificationWorkerPool(XRPLWorkerPoolBase[TransactionVerifyResult]):
    """
    Worker pool for concurrent transaction verification.

    Verifies that transactions have been finalized on the ledger.
    """

    def __init__(
        self,
        node_pool: XRPLNodePool,
        num_workers: int = CONSTANTS.VERIFICATION_WORKER_POOL_SIZE,
    ):
        super().__init__(
            node_pool=node_pool,
            pool_name="VerifyPool",
            num_workers=num_workers,
        )

    async def submit_verification(
        self,
        signed_tx: Transaction,
        prelim_result: str,
        timeout: float = CONSTANTS.VERIFY_TX_TIMEOUT,
    ) -> TransactionVerifyResult:
        """
        Submit a transaction for verification.

        Args:
            signed_tx: The signed transaction to verify
            prelim_result: The preliminary result from submission
            timeout: Maximum time to wait for verification

        Returns:
            TransactionVerifyResult with verification outcome
        """
        # Package the verification request
        request = {
            "signed_tx": signed_tx,
            "prelim_result": prelim_result,
        }
        return await self.submit(request, timeout=timeout)

    async def _process_task(
        self,
        task: WorkerTask,
        client: AsyncWebsocketClient,
    ) -> TransactionVerifyResult:
        """
        Verify a transaction's finality on the ledger.

        Args:
            task: The task containing verification request
            client: The client to use

        Returns:
            TransactionVerifyResult with verification outcome
        """
        request = task.request
        signed_tx: Transaction = request["signed_tx"]
        prelim_result: str = request["prelim_result"]

        # Only verify transactions that have a chance of success
        if prelim_result not in ("tesSUCCESS", "terQUEUED"):
            self.logger().warning(
                f"[VerifyPool] Transaction prelim_result={prelim_result} indicates failure"
            )
            return TransactionVerifyResult(
                verified=False,
                error=f"Preliminary result {prelim_result} indicates failure",
            )

        tx_hash = signed_tx.get_hash()
        self.logger().debug(
            f"[VerifyPool] Starting verification for tx_hash={tx_hash[:16]}..."
        )

        try:
            # Try primary verification method
            result = await self._verify_with_wait(signed_tx, prelim_result, client, task.timeout)
            if result.verified:
                return result

            # Fallback to direct hash query
            self.logger().warning(
                f"[VerifyPool] Primary verification failed for {tx_hash[:16]}, "
                f"trying fallback query..."
            )
            return await self._verify_with_hash_query(tx_hash, client)

        except (XRPLConnectionError, XRPLWebsocketException):
            # Re-raise connection errors for retry handling at the worker level
            raise

        except Exception as e:
            self.logger().error(f"[VerifyPool] Verification error: {e}")
            return TransactionVerifyResult(
                verified=False,
                error=str(e),
            )

    async def _verify_with_wait(
        self,
        signed_tx: Transaction,
        prelim_result: str,
        client: AsyncWebsocketClient,
        timeout: float,
    ) -> TransactionVerifyResult:
        """Verify using the wait_for_final_transaction_outcome method."""
        try:
            response = await asyncio.wait_for(
                _wait_for_final_transaction_outcome(
                    transaction_hash=signed_tx.get_hash(),
                    client=client,
                    prelim_result=prelim_result,
                    last_ledger_sequence=signed_tx.last_ledger_sequence,
                ),
                timeout=timeout,
            )

            final_result = response.result.get("meta", {}).get("TransactionResult", "unknown")

            self.logger().debug(
                f"[VerifyPool] Transaction verified: "
                f"hash={signed_tx.get_hash()[:16]}, result={final_result}"
            )

            return TransactionVerifyResult(
                verified=True,
                response=response,
                final_result=final_result,
            )

        except XRPLReliableSubmissionException as e:
            self.logger().error(f"[VerifyPool] Transaction failed on-chain: {e}")
            return TransactionVerifyResult(
                verified=False,
                error=f"Transaction failed: {e}",
            )

        except asyncio.TimeoutError:
            self.logger().warning("[VerifyPool] Verification timed out")
            return TransactionVerifyResult(
                verified=False,
                error="Verification timed out",
            )

        except (XRPLConnectionError, XRPLWebsocketException):
            # Re-raise connection errors for retry handling
            raise

        except Exception as e:
            self.logger().warning(f"[VerifyPool] Verification error: {e}")
            return TransactionVerifyResult(
                verified=False,
                error=str(e),
            )

    async def _verify_with_hash_query(
        self,
        tx_hash: str,
        client: AsyncWebsocketClient,
        max_attempts: int = 5,
        poll_interval: float = 3.0,
    ) -> TransactionVerifyResult:
        """Fallback verification by querying transaction hash directly."""
        self.logger().debug(
            f"[VerifyPool] Fallback query for tx_hash={tx_hash[:16]}..."
        )

        for attempt in range(max_attempts):
            try:
                tx_request = Tx(transaction=tx_hash)
                response = await client._request_impl(tx_request)

                if not response.is_successful():
                    error = response.result.get("error", "unknown")
                    if error == "txnNotFound":
                        self.logger().debug(
                            f"[VerifyPool] tx_hash={tx_hash[:16]} not found, "
                            f"attempt {attempt + 1}/{max_attempts}"
                        )
                    else:
                        self.logger().warning(
                            f"[VerifyPool] Error querying tx_hash={tx_hash[:16]}: {error}"
                        )
                else:
                    result = response.result
                    if result.get("validated", False):
                        final_result = result.get("meta", {}).get("TransactionResult", "unknown")
                        self.logger().debug(
                            f"[VerifyPool] Transaction found and validated: "
                            f"tx_hash={tx_hash[:16]}, result={final_result}"
                        )
                        return TransactionVerifyResult(
                            verified=final_result == "tesSUCCESS",
                            response=response,
                            final_result=final_result,
                        )
                    else:
                        self.logger().debug(
                            f"[VerifyPool] tx_hash={tx_hash[:16]} found but not validated yet"
                        )

            except XRPLConnectionError:
                # Re-raise for retry handling
                raise
            except KeyError as e:
                # KeyError can occur if the connection reconnects during the request,
                # which clears _open_requests in the XRPL library
                self.logger().warning(f"[VerifyPool] Request lost during client reconnection: {e}")
                raise XRPLConnectionError(f"Request lost during reconnection: {e}")
            except XRPLWebsocketException:
                # Re-raise for retry handling - websocket is not open
                raise
            except Exception as e:
                self.logger().warning(
                    f"[VerifyPool] Exception querying tx_hash={tx_hash[:16]}: {e}"
                )

            # Wait before next attempt
            if attempt < max_attempts - 1:
                await asyncio.sleep(poll_interval)

        return TransactionVerifyResult(
            verified=False,
            error=f"Transaction not found after {max_attempts} attempts",
        )


# ============================================
# Transaction Worker Pool
# ============================================

class XRPLTransactionWorkerPool(XRPLWorkerPoolBase[TransactionSubmitResult]):
    """
    Worker pool for transaction submissions.

    Features:
    - Concurrent transaction preparation (autofill, signing)
    - Serialized submission through a shared pipeline
    - Handles sequence error retries

    The pipeline ensures only one transaction is submitted at a time,
    preventing sequence number race conditions.
    """

    def __init__(
        self,
        node_pool: XRPLNodePool,
        wallet: Wallet,
        pipeline: "XRPLTransactionPipeline",
        num_workers: int = CONSTANTS.TX_WORKER_POOL_SIZE,
    ):
        """
        Initialize the transaction worker pool.

        Args:
            node_pool: The XRPL node pool
            wallet: The wallet for signing transactions
            pipeline: The shared transaction pipeline
            num_workers: Number of concurrent workers
        """
        super().__init__(
            node_pool=node_pool,
            pool_name=f"TxPool[{wallet.classic_address[:8]}]",
            num_workers=num_workers,
        )
        self._wallet = wallet
        self._pipeline = pipeline

    async def submit_transaction(
        self,
        transaction: Transaction,
        fail_hard: bool = True,
        max_retries: int = CONSTANTS.PLACE_ORDER_MAX_RETRY,
    ) -> TransactionSubmitResult:
        """
        Submit a transaction through the pool.

        Args:
            transaction: The unsigned transaction to submit
            fail_hard: Whether to use fail_hard mode
            max_retries: Maximum retry attempts for sequence errors

        Returns:
            TransactionSubmitResult with submission outcome
        """
        request = {
            "transaction": transaction,
            "fail_hard": fail_hard,
            "max_retries": max_retries,
        }
        return await self.submit(request, timeout=CONSTANTS.SUBMIT_TX_TIMEOUT * max_retries)

    async def _process_task(
        self,
        task: WorkerTask,
        client: AsyncWebsocketClient,
    ) -> TransactionSubmitResult:
        """
        Process a transaction submission task.

        This handles retries for sequence errors but delegates
        the actual submission to the pipeline for serialization.

        Args:
            task: The task containing transaction details
            client: The client to use (for autofill)

        Returns:
            TransactionSubmitResult with submission outcome
        """
        request = task.request
        transaction: Transaction = request["transaction"]
        fail_hard: bool = request.get("fail_hard", True)
        max_retries: int = request.get("max_retries", CONSTANTS.PLACE_ORDER_MAX_RETRY)

        submission_id = task.task_id
        self.logger().debug(f"[{self._pool_name}] Starting submission {submission_id}")

        submit_retry = 0
        last_error = None

        while submit_retry < max_retries:
            try:
                # Submit through pipeline - this serializes all submissions
                result = await self._submit_through_pipeline(
                    transaction, fail_hard, submission_id, client
                )

                # Handle successful submission
                if result.is_accepted:
                    self.logger().debug(
                        f"[{self._pool_name}] Submission {submission_id} accepted: "
                        f"prelim_result={result.prelim_result}, tx_hash={result.tx_hash}"
                    )
                    return result

                # Handle sequence errors - retry with fresh autofill
                if result.prelim_result in CONSTANTS.SEQUENCE_ERRORS:
                    submit_retry += 1
                    retry_interval = (
                        CONSTANTS.PRE_SEQ_RETRY_INTERVAL
                        if result.prelim_result == "terPRE_SEQ"
                        else CONSTANTS.PLACE_ORDER_RETRY_INTERVAL
                    )
                    self.logger().debug(
                        f"[{self._pool_name}] {submission_id} got {result.prelim_result}. "
                        f"Waiting {retry_interval}s and retrying... "
                        f"(Attempt {submit_retry}/{max_retries})"
                    )
                    await asyncio.sleep(retry_interval)
                    continue

                # Handle transient errors - retry
                if result.prelim_result in CONSTANTS.TRANSIENT_RETRY_ERRORS:
                    submit_retry += 1
                    self.logger().debug(
                        f"[{self._pool_name}] {submission_id} got {result.prelim_result}. "
                        f"Retrying... (Attempt {submit_retry}/{max_retries})"
                    )
                    await asyncio.sleep(CONSTANTS.PLACE_ORDER_RETRY_INTERVAL)
                    continue

                # Other error - don't retry
                self.logger().error(
                    f"[{self._pool_name}] {submission_id} failed: prelim_result={result.prelim_result}"
                )
                return result

            except XRPLTimeoutError as e:
                # Timeout - DO NOT retry as transaction may have succeeded
                self.logger().error(
                    f"[{self._pool_name}] {submission_id} timed out: {e}. "
                    f"NOT retrying to avoid duplicate transactions."
                )
                return TransactionSubmitResult(
                    success=False,
                    error=f"Timeout: {e}",
                )

            except XRPLConnectionError:
                # Re-raise for retry handling at pool level
                raise

            except Exception as e:
                last_error = str(e)
                self.logger().error(f"[{self._pool_name}] {submission_id} error: {e}")
                submit_retry += 1
                if submit_retry < max_retries:
                    await asyncio.sleep(CONSTANTS.PLACE_ORDER_RETRY_INTERVAL)

        return TransactionSubmitResult(
            success=False,
            error=f"Max retries ({max_retries}) reached: {last_error}",
        )

    async def _submit_through_pipeline(
        self,
        transaction: Transaction,
        fail_hard: bool,
        submission_id: str,
        client: AsyncWebsocketClient,
    ) -> TransactionSubmitResult:
        """
        Execute the actual submission through the pipeline.

        This ensures only one transaction is autofilled/submitted at a time,
        preventing sequence number race conditions.

        Args:
            transaction: The transaction to submit
            fail_hard: Whether to use fail_hard mode
            submission_id: Identifier for tracing
            client: The client to use

        Returns:
            TransactionSubmitResult with outcome
        """
        async def _do_submit():
            self.logger().debug(f"[{self._pool_name}] {submission_id}: Autofilling transaction...")
            filled_tx = await autofill(transaction, client)

            self.logger().debug(
                f"[{self._pool_name}] {submission_id}: Autofill done, "
                f"sequence={filled_tx.sequence}, "
                f"last_ledger={filled_tx.last_ledger_sequence}"
            )

            # Sign the transaction
            signed_tx = sign(filled_tx, self._wallet)
            tx_hash = signed_tx.get_hash()

            self.logger().debug(
                f"[{self._pool_name}] {submission_id}: Submitting to XRPL, tx_hash={tx_hash[:8]}..."
            )

            # Submit
            tx_blob = encode(signed_tx.to_xrpl())
            response = await client._request_impl(
                SubmitOnly(tx_blob=tx_blob, fail_hard=fail_hard),
                timeout=CONSTANTS.REQUEST_TIMEOUT,
            )

            return signed_tx, response

        # Submit through the pipeline
        signed_tx, response = await self._pipeline.submit(_do_submit(), submission_id)

        prelim_result = response.result.get("engine_result", "UNKNOWN")
        tx_hash = signed_tx.get_hash()
        tx_hash_prefix = tx_hash[:6]
        exchange_order_id = f"{signed_tx.sequence}-{signed_tx.last_ledger_sequence}-{tx_hash_prefix}"

        self.logger().debug(
            f"[{self._pool_name}] {submission_id}: Complete, "
            f"exchange_order_id={exchange_order_id}, prelim_result={prelim_result}"
        )

        return TransactionSubmitResult(
            success=prelim_result in ("tesSUCCESS", "terQUEUED"),
            signed_tx=signed_tx,
            response=response,
            prelim_result=prelim_result,
            exchange_order_id=exchange_order_id,
            tx_hash=tx_hash,
        )
