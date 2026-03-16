"""
Shared retry logic for Gateway executors (LPExecutor, SwapExecutor).

Provides GatewayRetryMixin for handling transaction failures with configurable
retry behavior including timeout detection and recoverable error handling.
"""
from enum import Enum
from typing import List, Optional


class RetryAction(Enum):
    """Action returned by handle_gateway_failure to guide caller behavior."""
    RETRY = "RETRY"   # Increment counter, retry operation
    SKIP = "SKIP"     # Recoverable error, retry without counting
    STOP = "STOP"     # Max retries reached, stop executor


class GatewayRetryMixin:
    """
    Mixin providing retry logic for Gateway executors.

    Tracks retry state and determines appropriate action for failures.
    Expects the class to have:
    - logger() method returning a logger
    - _strategy attribute for notifications (optional)
    """

    _current_retries: int
    _max_retries: int
    _max_retries_reached: bool

    def init_retry_state(self, max_retries: int = 10):
        """Initialize retry tracking state."""
        self._current_retries = 0
        self._max_retries = max_retries
        self._max_retries_reached = False

    def reset_retry_state(self):
        """Reset retry counter after successful operation."""
        self._current_retries = 0
        self._max_retries_reached = False

    def handle_gateway_failure(
        self,
        error: Exception,
        operation: str,
        trading_pair: str,
        signature: Optional[str] = None,
        recoverable_errors: Optional[List[str]] = None,
    ) -> RetryAction:
        """
        Handle a gateway operation failure with retry logic.

        Args:
            error: The exception that occurred
            operation: Description of the operation (e.g., "SWAP BUY", "LP OPEN")
            trading_pair: Trading pair for logging
            signature: Optional transaction signature for logging
            recoverable_errors: List of error substrings that indicate recoverable errors
                              (will retry without incrementing counter)

        Returns:
            RetryAction indicating what the caller should do
        """
        error_str = str(error)
        sig_info = f" [sig: {signature}]" if signature else ""
        recoverable_errors = recoverable_errors or []

        # Check for recoverable errors (retry without incrementing counter)
        for recoverable in recoverable_errors:
            if recoverable in error_str:
                self.logger().info(f"{operation} recoverable error: {recoverable}")
                return RetryAction.SKIP

        self._current_retries += 1
        is_timeout = "TRANSACTION_TIMEOUT" in error_str

        if self._current_retries >= self._max_retries:
            msg = (
                f"{operation} FAILED after {self._max_retries} retries for {trading_pair}.{sig_info} "
                f"Manual intervention required. Error: {error}"
            )
            self.logger().error(msg)
            if hasattr(self, '_strategy') and self._strategy and hasattr(self._strategy, 'notify_hb_app_with_timestamp'):
                self._strategy.notify_hb_app_with_timestamp(msg)
            self._max_retries_reached = True
            return RetryAction.STOP

        if is_timeout:
            self.logger().warning(
                f"{operation} timeout (retry {self._current_retries}/{self._max_retries}).{sig_info} "
                "Chain may be congested. Retrying..."
            )
        else:
            self.logger().warning(
                f"{operation} failed (retry {self._current_retries}/{self._max_retries}): {error}"
            )

        return RetryAction.RETRY
