"""
XRPL Worker Pool Manager

Centralized manager for XRPL worker pools and transaction pipeline.

This module provides:
- Factory methods for getting worker pools
- Lifecycle management for all pools and pipeline

Pool Types:
- QueryPool: Concurrent read-only queries
- VerificationPool: Concurrent transaction verification
- TransactionPool: Concurrent prep, serialized submit (per wallet)

Re-exports:
- Result dataclasses: QueryResult, TransactionSubmitResult, TransactionVerifyResult
"""
import logging
from typing import Dict, Optional

from xrpl.wallet import Wallet

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_transaction_pipeline import XRPLTransactionPipeline
from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLNodePool
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import (  # Re-export result dataclasses for convenient access
    XRPLQueryWorkerPool,
    XRPLTransactionWorkerPool,
    XRPLVerificationWorkerPool,
)
from hummingbot.logger import HummingbotLogger

# ============================================
# Request Priority Enum (kept for API compatibility)
# ============================================


class RequestPriority:
    """
    Priority levels for XRPL requests.

    Note: Deprecated. Kept for API compatibility only.
    The new pool-based architecture handles prioritization differently.
    """
    LOW = 1       # Balance updates, order book queries
    MEDIUM = 2    # Order status, transaction verification
    HIGH = 3      # Order submission, cancellation
    CRITICAL = 4  # Emergency operations


# ============================================
# Worker Pool Manager
# ============================================
class XRPLWorkerPoolManager:
    """
    Centralized manager for XRPL worker pools.

    Features:
    - Lazy pool initialization
    - Transaction pipeline for serialization
    - Factory methods for getting pools

    Pool Architecture:
    - QueryPool: Multiple concurrent workers for read-only queries
    - VerificationPool: Multiple concurrent workers for tx verification
    - TransactionPool: Multiple concurrent workers, serialized through pipeline

    Usage:
        manager = XRPLWorkerPoolManager(node_pool)

        # Get pools (lazy initialized)
        query_pool = manager.get_query_pool()
        verify_pool = manager.get_verification_pool()
        tx_pool = manager.get_transaction_pool(wallet)

        # Use pools
        result = await query_pool.submit(AccountInfo(...))
        verify_result = await verify_pool.submit_verification(signed_tx, prelim_result)
        submit_result = await tx_pool.submit_transaction(transaction)
    """
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        node_pool: "XRPLNodePool",
        query_pool_size: int = CONSTANTS.QUERY_WORKER_POOL_SIZE,
        verification_pool_size: int = CONSTANTS.VERIFICATION_WORKER_POOL_SIZE,
        transaction_pool_size: int = CONSTANTS.TX_WORKER_POOL_SIZE,
    ):
        """
        Initialize the worker pool manager.

        Args:
            node_pool: The XRPLNodePool to get connections from
            num_workers: Legacy parameter, kept for API compatibility
            max_queue_size: Legacy parameter, kept for API compatibility
        """
        self._node_pool = node_pool
        self._running = False

        # Transaction pipeline (singleton, shared by all tx pools)
        self._pipeline: Optional[XRPLTransactionPipeline] = None

        # Worker pools (lazy initialization)
        self._query_pool: Optional[XRPLQueryWorkerPool] = None
        self._verification_pool: Optional[XRPLVerificationWorkerPool] = None
        # Per-wallet transaction pools
        self._transaction_pools: Dict[str, XRPLTransactionWorkerPool] = {}

        # Pool sizes
        self._query_pool_size = query_pool_size
        self._verification_pool_size = verification_pool_size
        self._transaction_pool_size = transaction_pool_size

    @property
    def node_pool(self) -> XRPLNodePool:
        """Get the node pool for direct access when needed."""
        return self._node_pool

    @property
    def pipeline(self) -> XRPLTransactionPipeline:
        """Get or create the shared transaction pipeline."""
        if self._pipeline is None:
            self._pipeline = XRPLTransactionPipeline()
        return self._pipeline

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    def is_running(self) -> bool:
        """Check if the worker pool manager is currently running."""
        return self._running

    # ============================================
    # Pool Factory Methods (New API)
    # ============================================

    def get_query_pool(self) -> XRPLQueryWorkerPool:
        """
        Get or create the shared query worker pool.

        Query pools are safe to share since they're stateless and concurrent.
        The pool is lazily started on first submit.

        Returns:
            XRPLQueryWorkerPool instance
        """
        if self._query_pool is None:
            self._query_pool = XRPLQueryWorkerPool(
                node_pool=self._node_pool,
                num_workers=self._query_pool_size,
            )
            self.logger().debug(
                f"Created query pool with {self._query_pool_size} workers"
            )
        return self._query_pool

    def get_verification_pool(self) -> XRPLVerificationWorkerPool:
        """
        Get or create the shared verification worker pool.

        Verification pools are safe to share since they're stateless and concurrent.
        The pool is lazily started on first submit.

        Returns:
            XRPLVerificationWorkerPool instance
        """
        if self._verification_pool is None:
            self._verification_pool = XRPLVerificationWorkerPool(
                node_pool=self._node_pool,
                num_workers=self._verification_pool_size,
            )
            self.logger().debug(
                f"Created verification pool with {self._verification_pool_size} workers"
            )
        return self._verification_pool

    def get_transaction_pool(
        self,
        wallet: Wallet,
        pool_id: Optional[str] = None,
    ) -> XRPLTransactionWorkerPool:
        """
        Get or create a transaction worker pool for a specific wallet.

        Each wallet gets its own transaction pool, but all pools share
        the same pipeline for serialized submission.

        Args:
            wallet: The wallet to use for signing transactions
            pool_id: Optional identifier for the pool (defaults to wallet address)

        Returns:
            XRPLTransactionWorkerPool instance
        """
        if pool_id is None:
            pool_id = wallet.classic_address

        if pool_id not in self._transaction_pools:
            self._transaction_pools[pool_id] = XRPLTransactionWorkerPool(
                node_pool=self._node_pool,
                wallet=wallet,
                pipeline=self.pipeline,
                num_workers=self._transaction_pool_size,
            )
            self.logger().debug(
                f"Created transaction pool for {pool_id[:8]}... "
                f"with {self._transaction_pool_size} workers"
            )
        return self._transaction_pools[pool_id]

    @property
    def pipeline_queue_size(self) -> int:
        """Return the current pipeline queue size."""
        if self._pipeline is None:
            return 0
        return self._pipeline.queue_size

    # ============================================
    # Lifecycle Management
    # ============================================

    async def start(self):
        """Start the worker pool manager and all pools."""
        if self._running:
            self.logger().warning("Worker pool manager is already running")
            return

        self._running = True
        self.logger().debug("Starting worker pool manager...")

        # Start the pipeline
        await self.pipeline.start()

        # Start any existing pools
        if self._query_pool is not None:
            await self._query_pool.start()
        if self._verification_pool is not None:
            await self._verification_pool.start()
        for pool in self._transaction_pools.values():
            await pool.start()

        self.logger().debug("Worker pool manager started")

    async def stop(self):
        """Stop all pools and the pipeline."""
        if not self._running:
            self.logger().warning("Worker pool manager is not running")
            return

        self._running = False
        self.logger().debug("Stopping worker pool manager...")

        # Stop all pools
        if self._query_pool is not None:
            await self._query_pool.stop()
        if self._verification_pool is not None:
            await self._verification_pool.stop()
        for pool in self._transaction_pools.values():
            await pool.stop()

        # Stop the pipeline
        if self._pipeline is not None:
            await self._pipeline.stop()

        self.logger().debug("Worker pool manager stopped")

    # ============================================
    # Statistics and Monitoring
    # ============================================

    def get_stats(self) -> Dict[str, any]:
        """
        Get aggregated statistics from all pools and pipeline.

        Returns:
            Dictionary with stats from all components
        """
        stats = {
            "running": self._running,
            "pipeline": self.pipeline.stats if self._pipeline else None,
            "pools": {},
        }

        if self._query_pool is not None:
            stats["pools"]["query"] = self._query_pool.stats.to_dict()
        if self._verification_pool is not None:
            stats["pools"]["verification"] = self._verification_pool.stats.to_dict()

        for pool_id, pool in self._transaction_pools.items():
            stats["pools"][f"tx_{pool_id[:8]}"] = pool.stats.to_dict()

        return stats
