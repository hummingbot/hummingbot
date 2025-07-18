"""
Simple transaction monitor for Gateway transactions.
"""
import asyncio
import inspect
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
        self._active_monitors = set()  # Track active transaction hashes to prevent duplicates

    async def monitor_transaction(
        self,
        response: Dict[str, Any],
        chain: str,
        network: str,
        order_id: str,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Monitor a transaction until confirmed/failed/timeout.

        :param response: Initial Gateway response with signature and status
        :param chain: Blockchain chain name
        :param network: Network name
        :param order_id: Order ID for tracking
        :param callback: Callback function(event_type, order_id, data)
        """
        # Get signature from response (used for all chains)
        signature = response.get("signature", "")
        # Check for txStatus (Solana) or status (EVM)
        # Convert to int to handle string values from gateway
        try:
            status = int(response.get("txStatus", response.get("status", self.STATUS_PENDING)))
        except (ValueError, TypeError):
            status = self.STATUS_PENDING

        self.logger().info(f"Transaction monitor: signature={signature}, status={status}, order_id={order_id}")

        if not signature:
            self.logger().warning(f"No signature in response for order {order_id}")
            return

        # Check if we're already monitoring this transaction
        if signature in self._active_monitors:
            self.logger().warning(f"Already monitoring transaction {signature} - skipping duplicate monitor request")
            return

        # Add to active monitors
        self._active_monitors.add(signature)
        self.logger().info(f"Starting to monitor transaction {signature}")

        # Notify callback of transaction signature
        if callback:
            await self._invoke_callback(callback, "tx_hash", order_id, signature)

        # Check if already completed
        if status == self.STATUS_CONFIRMED:
            self.logger().info(f"Transaction {signature} already confirmed on initial check")
            if callback:
                await self._invoke_callback(callback, "confirmed", order_id, response)
            self._active_monitors.discard(signature)
            self.logger().info(f"Stopped monitoring transaction {signature} - already confirmed")
            return
        elif status == self.STATUS_FAILED:
            if callback:
                await self._invoke_callback(callback, "failed", order_id, response.get("message", "Transaction failed"))
            self._active_monitors.discard(signature)
            return

        # Status is PENDING - start polling
        self.logger().info(f"Transaction {signature} is pending, starting polling")
        await self._poll_until_complete(signature, chain, network, order_id, callback)

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

        :param tx_hash: Transaction signature to poll
        :param chain: Blockchain chain name
        :param network: Network name
        :param order_id: Order ID for tracking
        :param callback: Callback function
        """
        max_attempts = int(self.MAX_POLL_TIME / self.POLL_INTERVAL) if self.POLL_INTERVAL > 0 else int(self.MAX_POLL_TIME * 10)

        for attempt in range(max_attempts):
            await asyncio.sleep(self.POLL_INTERVAL)

            try:
                # Poll transaction status using signature
                poll_response = await self._client.get_transaction_status(
                    chain,
                    network,
                    tx_hash
                )

                # Check for txStatus (Solana) or status (EVM)
                # Convert to int to handle string values from gateway
                try:
                    status = int(poll_response.get("txStatus", poll_response.get("status", self.STATUS_PENDING)))
                except (ValueError, TypeError):
                    status = self.STATUS_PENDING
                self.logger().debug(f"Poll response for {tx_hash}: status={status}, response={poll_response}")

                if status == self.STATUS_CONFIRMED:
                    self.logger().info(f"Transaction {tx_hash} confirmed for order {order_id}")
                    if callback:
                        self.logger().debug(f"Invoking callback for confirmed transaction {tx_hash}")
                        await self._invoke_callback(callback, "confirmed", order_id, poll_response)
                    else:
                        self.logger().warning(f"No callback provided for confirmed transaction {tx_hash}")
                    self._active_monitors.discard(tx_hash)
                    self.logger().info(f"Stopped polling {tx_hash} - confirmed")
                    return
                elif status == self.STATUS_FAILED:
                    self.logger().info(f"Transaction {tx_hash} failed for order {order_id}")
                    if callback:
                        await self._invoke_callback(callback, "failed", order_id, poll_response.get("message", "Transaction failed"))
                    self._active_monitors.discard(tx_hash)
                    return

                # Still pending, continue polling
                self.logger().debug(f"Transaction signature {tx_hash} still pending (attempt {attempt + 1}/{max_attempts})")

            except Exception as e:
                self.logger().debug(f"Error polling transaction signature {tx_hash}: {e}")
                # Continue polling even on error

        # Timeout reached
        self.logger().warning(f"Transaction signature {tx_hash} timed out after {self.MAX_POLL_TIME}s for order {order_id}")
        if callback:
            await self._invoke_callback(callback, "failed", order_id, f"Transaction timed out after {self.MAX_POLL_TIME} seconds")
        self._active_monitors.discard(tx_hash)

    async def _invoke_callback(self, callback: Callable, event_type: str, order_id: str, data: Any) -> None:
        """
        Invoke callback function, handling both sync and async callbacks.

        :param callback: Callback function
        :param event_type: Event type
        :param order_id: Order ID
        :param data: Event data
        """
        if inspect.iscoroutinefunction(callback):
            await callback(event_type, order_id, data)
        else:
            callback(event_type, order_id, data)
