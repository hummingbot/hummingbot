"""
Simple transaction monitor for Gateway transactions.
"""
import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.gateway.core import GatewayClient


class TransactionMonitor:
    """
    Monitors Gateway transaction status until confirmed/failed/timeout.
    Uses simple polling mechanism without transaction retry.
    """

    _logger: Optional[HummingbotLogger] = None

    # Transaction status constants from Gateway
    STATUS_PENDING = 0
    STATUS_CONFIRMED = 1
    STATUS_FAILED = -1

    # Polling configuration
    POLL_INTERVAL = 2.0  # seconds
    MAX_POLL_TIME = 30.0  # seconds

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, gateway_client: "GatewayClient"):
        """
        Initialize transaction monitor.

        :param gateway_client: GatewayClient instance for polling
        """
        self._client = gateway_client

    async def monitor_transaction(
        self,
        response: Dict[str, Any],
        chain: str,
        network: str,
        order_id: str,
        callback: Optional[Callable] = None
    ) -> None:
        """
        Monitor a transaction until confirmed/failed/timeout.

        :param response: Initial Gateway response with txHash and status
        :param chain: Blockchain chain name
        :param network: Network name
        :param order_id: Order ID for tracking
        :param callback: Callback function(event_type, order_id, data)
        """
        tx_hash = response.get("txHash", "")
        status = response.get("status", self.STATUS_PENDING)

        if not tx_hash:
            self.logger().warning(f"No transaction hash in response for order {order_id}")
            return

        # Notify callback of transaction hash
        if callback:
            callback("tx_hash", order_id, tx_hash)

        # Check if already completed
        if status == self.STATUS_CONFIRMED:
            if callback:
                callback("confirmed", order_id, response)
            return
        elif status == self.STATUS_FAILED:
            if callback:
                callback("failed", order_id, response.get("message", "Transaction failed"))
            return

        # Status is PENDING - start polling
        await self._poll_until_complete(tx_hash, chain, network, order_id, callback)

    async def _poll_until_complete(
        self,
        tx_hash: str,
        chain: str,
        network: str,
        order_id: str,
        callback: Optional[Callable]
    ) -> None:
        """
        Poll transaction status until complete or timeout.

        :param tx_hash: Transaction hash to poll
        :param chain: Blockchain chain name
        :param network: Network name
        :param order_id: Order ID for tracking
        :param callback: Callback function
        """
        max_attempts = int(self.MAX_POLL_TIME / self.POLL_INTERVAL) if self.POLL_INTERVAL > 0 else int(self.MAX_POLL_TIME * 10)

        for attempt in range(max_attempts):
            await asyncio.sleep(self.POLL_INTERVAL)

            try:
                # Poll transaction status
                poll_response = await self._client.get_transaction_status(
                    chain,
                    network,
                    tx_hash
                )

                status = poll_response.get("status", self.STATUS_PENDING)

                if status == self.STATUS_CONFIRMED:
                    self.logger().info(f"Transaction {tx_hash} confirmed for order {order_id}")
                    if callback:
                        callback("confirmed", order_id, poll_response)
                    return
                elif status == self.STATUS_FAILED:
                    self.logger().info(f"Transaction {tx_hash} failed for order {order_id}")
                    if callback:
                        callback("failed", order_id, poll_response.get("message", "Transaction failed"))
                    return

                # Still pending, continue polling
                self.logger().debug(f"Transaction {tx_hash} still pending (attempt {attempt + 1}/{max_attempts})")

            except Exception as e:
                self.logger().debug(f"Error polling transaction {tx_hash}: {e}")
                # Continue polling even on error

        # Timeout reached
        self.logger().warning(f"Transaction {tx_hash} timed out after {self.MAX_POLL_TIME}s for order {order_id}")
        if callback:
            callback("failed", order_id, f"Transaction timed out after {self.MAX_POLL_TIME} seconds")
