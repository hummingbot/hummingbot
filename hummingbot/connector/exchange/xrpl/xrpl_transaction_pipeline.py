"""
XRPL Transaction Pipeline

Serializes all XRPL transaction submissions to prevent sequence number race conditions.

Architecture:
- Single FIFO queue for all transaction submissions
- Pipeline loop processes one transaction at a time
- Configurable delay between submissions
- Since only one transaction is processed at a time, autofill always gets the correct sequence

This pipeline is shared across all wallet-specific transaction pools to ensure
global serialization of transaction submissions.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Optional, Tuple

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLSystemBusyError
from hummingbot.logger import HummingbotLogger


class XRPLTransactionPipeline:
    """
    Serialized transaction submission pipeline for XRPL.

    All transaction submissions go through this pipeline to ensure:
    1. Only one transaction is processed at a time
    2. Proper spacing between submissions
    3. Sequence numbers are correctly assigned by autofill

    This prevents race conditions where multiple concurrent autofills
    could get the same sequence number.
    """
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        max_queue_size: int = CONSTANTS.PIPELINE_MAX_QUEUE_SIZE,
        submission_delay_ms: int = CONSTANTS.PIPELINE_SUBMISSION_DELAY_MS,
    ):
        """
        Initialize the transaction pipeline.

        Args:
            max_queue_size: Maximum pending submissions in the queue
            submission_delay_ms: Delay in milliseconds between submissions
        """
        self._max_queue_size = max_queue_size
        self._delay_seconds = submission_delay_ms / 1000.0

        # FIFO queue: (coroutine, future, submission_id)
        self._submission_queue: asyncio.Queue[Tuple[Awaitable, asyncio.Future, str]] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._pipeline_task: Optional[asyncio.Task] = None
        self._running = False
        self._started = False  # For lazy initialization

        # Statistics
        self._submissions_processed = 0
        self._submissions_failed = 0
        self._total_latency_ms = 0.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    def is_running(self) -> bool:
        """Check if the pipeline is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._submission_queue.qsize()

    @property
    def stats(self) -> dict:
        """Get pipeline statistics."""
        total = self._submissions_processed + self._submissions_failed
        avg_latency = self._total_latency_ms / total if total > 0 else 0.0
        return {
            "queue_size": self.queue_size,
            "submissions_processed": self._submissions_processed,
            "submissions_failed": self._submissions_failed,
            "avg_latency_ms": round(avg_latency, 2),
        }

    async def start(self):
        """Start the pipeline loop."""
        if self._running:
            self.logger().warning("[PIPELINE] Pipeline is already running")
            return

        self._running = True
        self._started = True
        self._pipeline_task = asyncio.create_task(self._pipeline_loop())

        self.logger().debug(
            f"[PIPELINE] Started with {self._delay_seconds * 1000:.0f}ms delay between submissions"
        )

    async def stop(self):
        """Stop the pipeline and cancel pending submissions."""
        if not self._running:
            return

        self._running = False
        self.logger().debug("[PIPELINE] Stopping...")

        # Cancel pipeline task
        if self._pipeline_task is not None:
            self._pipeline_task.cancel()
            try:
                await self._pipeline_task
            except asyncio.CancelledError:
                pass
            self._pipeline_task = None

        # Cancel pending submissions
        cancelled_count = 0
        while not self._submission_queue.empty():
            try:
                _, future, submission_id = self._submission_queue.get_nowait()
                if not future.done():
                    future.cancel()
                    cancelled_count += 1
                    self.logger().debug(f"[PIPELINE] Cancelled pending submission {submission_id}")
            except asyncio.QueueEmpty:
                break

        self.logger().debug(
            f"[PIPELINE] Stopped, cancelled {cancelled_count} pending submissions"
        )

    async def _ensure_started(self):
        """Ensure the pipeline is started (lazy initialization)."""
        if not self._started:
            await self.start()

    async def submit(
        self,
        coro: Awaitable,
        submission_id: Optional[str] = None,
    ) -> Any:
        """
        Submit a coroutine to the serialized pipeline.

        All XRPL transaction submissions should go through this method
        to ensure they are processed one at a time.

        Args:
            coro: The coroutine to execute (typically autofill/sign/submit)
            submission_id: Optional identifier for tracing

        Returns:
            The result from the coroutine

        Raises:
            XRPLSystemBusyError: If the pipeline queue is full
            Exception: Any exception raised by the coroutine
        """
        # Lazy start
        await self._ensure_started()

        if not self._running:
            raise XRPLSystemBusyError("Pipeline is not running")

        # Generate submission_id if not provided
        if submission_id is None:
            submission_id = str(uuid.uuid4())[:8]

        # Create future for the result
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        # Add to FIFO queue
        try:
            queue_size_before = self._submission_queue.qsize()
            self._submission_queue.put_nowait((coro, future, submission_id))
            self.logger().debug(
                f"[PIPELINE] Queued submission {submission_id} "
                f"(queue_size: {queue_size_before} -> {queue_size_before + 1})"
            )
        except asyncio.QueueFull:
            self.logger().error(
                f"[PIPELINE] Queue full! Rejecting submission {submission_id} "
                f"(max={self._max_queue_size})"
            )
            raise XRPLSystemBusyError("Pipeline queue is full, try again later")

        # Wait for result
        return await future

    async def _pipeline_loop(self):
        """
        Pipeline loop that serializes transaction submissions.

        Processes submissions one at a time with a configurable delay.
        Since only one transaction is processed at a time, autofill
        will always get the correct sequence number.
        """
        self.logger().debug("[PIPELINE] Loop started")

        while self._running:
            try:
                # Get next submission with timeout
                try:
                    coro, future, submission_id = await asyncio.wait_for(
                        self._submission_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Skip if future was already cancelled
                if future.done():
                    self.logger().debug(f"[PIPELINE] Skipping cancelled submission {submission_id}")
                    continue

                self._submissions_processed += 1
                queue_size = self._submission_queue.qsize()
                self.logger().debug(
                    f"[PIPELINE] Processing submission {submission_id} "
                    f"(#{self._submissions_processed}, queue_remaining={queue_size})"
                )

                # Execute the submission coroutine
                start_time = time.time()
                try:
                    result = await coro
                    elapsed_ms = (time.time() - start_time) * 1000
                    self._total_latency_ms += elapsed_ms

                    if not future.done():
                        future.set_result(result)

                    self.logger().debug(
                        f"[PIPELINE] Submission {submission_id} completed in {elapsed_ms:.1f}ms"
                    )

                except Exception as e:
                    elapsed_ms = (time.time() - start_time) * 1000
                    self._total_latency_ms += elapsed_ms
                    self._submissions_failed += 1

                    if not future.done():
                        future.set_exception(e)

                    self.logger().error(
                        f"[PIPELINE] Submission {submission_id} failed after {elapsed_ms:.1f}ms: {e}"
                    )

                # Delay before allowing next submission
                self.logger().debug(
                    f"[PIPELINE] Waiting {self._delay_seconds * 1000:.0f}ms before next submission"
                )
                await asyncio.sleep(self._delay_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger().error(f"[PIPELINE] Unexpected error: {e}")

        self.logger().debug(
            f"[PIPELINE] Loop stopped (processed {self._submissions_processed} submissions)"
        )
