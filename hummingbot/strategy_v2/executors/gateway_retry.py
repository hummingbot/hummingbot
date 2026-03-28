"""
Shared retry logic for Gateway executors (LPExecutor, SwapExecutor).

Provides GatewayRetryMixin for handling transaction failures with configurable
retry behavior including timeout detection and recoverable error handling.

Error Classification (via Gateway error codes):
- TRANSACTION_TIMEOUT: Transaction submitted but confirmation timed out. Retry is worthwhile
  because the tx may have succeeded or network congestion may clear.
- SIMULATION_FAILED, INSUFFICIENT_BALANCE, SLIPPAGE_EXCEEDED: Non-retryable errors.
  Transaction would fail on-chain. Do NOT retry - parameters are invalid or market conditions changed.
"""
import re
from enum import Enum
from typing import List, Optional


class RetryAction(Enum):
    """Action returned by handle_gateway_failure to guide caller behavior."""
    RETRY = "RETRY"           # Timeout error, retry operation (increment counter)
    SKIP = "SKIP"             # Recoverable error, retry without counting
    STOP = "STOP"             # Max retries reached, stop executor
    FAIL_IMMEDIATE = "FAIL"   # Non-retryable error (simulation failed), stop immediately


# Gateway error codes that are NOT retryable
# These match the ErrorCode constants in gateway/src/services/error-handler.ts
NON_RETRYABLE_ERROR_CODES = {
    "SIMULATION_FAILED",      # Transaction would fail on-chain
    "INSUFFICIENT_BALANCE",   # Not enough funds
    "SLIPPAGE_EXCEEDED",      # Price moved beyond tolerance
    "INVALID_PARAMS",         # Bad request parameters
}

# The only retryable error code
RETRYABLE_ERROR_CODE = "TRANSACTION_TIMEOUT"


def extract_error_code(error_str: str) -> Optional[str]:
    """Extract Gateway error code from error string.

    Gateway formats errors as: "Gateway error: ... [code: ERROR_CODE]"
    """
    match = re.search(r'\[code:\s*(\w+)\]', error_str)
    return match.group(1) if match else None


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

        # Extract Gateway error code if present
        error_code = extract_error_code(error_str)

        # Check for recoverable errors (retry without incrementing counter)
        for recoverable in recoverable_errors:
            if recoverable in error_str:
                self.logger().info(f"{operation} recoverable error: {recoverable}")
                return RetryAction.SKIP

        # Check error code for non-retryable errors
        if error_code and error_code in NON_RETRYABLE_ERROR_CODES:
            msg = (
                f"{operation} FAILED for {trading_pair}: {error}. "
                f"Error code {error_code} is not retryable."
            )
            self.logger().error(msg)
            if hasattr(self, '_strategy') and self._strategy and hasattr(self._strategy, 'notify_hb_app_with_timestamp'):
                self._strategy.notify_hb_app_with_timestamp(msg)
            self._max_retries_reached = True
            return RetryAction.FAIL_IMMEDIATE

        # Check for timeout (retryable)
        is_timeout = error_code == RETRYABLE_ERROR_CODE or "TRANSACTION_TIMEOUT" in error_str

        if not is_timeout:
            # No error code and not a timeout - fail immediately
            # This handles legacy errors or unexpected error formats
            msg = (
                f"{operation} FAILED for {trading_pair}: {error}. "
                "Error is not retryable."
            )
            self.logger().error(msg)
            if hasattr(self, '_strategy') and self._strategy and hasattr(self._strategy, 'notify_hb_app_with_timestamp'):
                self._strategy.notify_hb_app_with_timestamp(msg)
            self._max_retries_reached = True
            return RetryAction.FAIL_IMMEDIATE

        # Timeout error - worth retrying
        self._current_retries += 1

        if self._current_retries >= self._max_retries:
            msg = (
                f"{operation} FAILED after {self._max_retries} timeout retries for {trading_pair}.{sig_info} "
                f"Manual intervention required. Error: {error}"
            )
            self.logger().error(msg)
            if hasattr(self, '_strategy') and self._strategy and hasattr(self._strategy, 'notify_hb_app_with_timestamp'):
                self._strategy.notify_hb_app_with_timestamp(msg)
            self._max_retries_reached = True
            return RetryAction.STOP

        self.logger().warning(
            f"{operation} timeout (retry {self._current_retries}/{self._max_retries}).{sig_info} "
            "Chain may be congested. Retrying..."
        )

        return RetryAction.RETRY
