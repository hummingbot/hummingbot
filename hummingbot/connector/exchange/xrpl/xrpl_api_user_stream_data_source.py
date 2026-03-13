"""
XRPL API User Stream Data Source

Polling-based user stream data source that periodically fetches account state
from the XRPL ledger instead of relying on WebSocket subscriptions.
"""
import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Deque, Dict, List, Optional, Set

from xrpl.models import AccountTx, Ledger

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_worker_manager import XRPLWorkerPoolManager
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import XRPLQueryWorkerPool
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class XRPLAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Polling-based user stream data source for XRPL.

    Instead of relying on WebSocket subscriptions (which can be unreliable),
    this data source periodically polls the account's transaction history
    to detect balance changes and order updates.

    Features:
    - Polls account transactions at configurable intervals
    - Tracks ledger index for incremental fetching
    - Deduplicates transactions to avoid processing the same event twice
    - Transforms XRPL transactions into internal event format
    """
    _logger: Optional[HummingbotLogger] = None

    POLL_INTERVAL = CONSTANTS.POLLING_INTERVAL

    def __init__(
        self,
        auth: XRPLAuth,
        connector: "XrplExchange",
        worker_manager: Optional[XRPLWorkerPoolManager] = None,
    ):
        """
        Initialize the polling data source.

        Args:
            auth: XRPL authentication handler
            connector: The XRPL exchange connector
            worker_manager: Optional worker manager for executing queries
        """
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._worker_manager = worker_manager

        # Polling state
        self._last_ledger_index: Optional[int] = None
        self._last_recv_time: float = 0
        # Use both deque for FIFO ordering and set for O(1) lookup
        self._seen_tx_hashes_queue: Deque[str] = deque()
        self._seen_tx_hashes_set: Set[str] = set()
        self._seen_tx_hashes_max_size = CONSTANTS.SEEN_TX_HASHES_MAX_SIZE

    # @classmethod
    # def logger(cls) -> HummingbotLogger:
    #     if cls._logger is None:
    #         cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
    #     return cls._logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message.

        :return: the timestamp of the last received message in seconds
        """
        return self._last_recv_time

    async def _initialize_ledger_index(self):
        """
        Initialize the last_ledger_index to the current validated ledger.

        This ensures we only process transactions that occur after the bot starts,
        rather than processing the entire account history.
        """
        try:
            if self._worker_manager is not None:
                # Use worker manager to get current ledger
                query_pool: XRPLQueryWorkerPool = self._worker_manager.get_query_pool()
                query_result = await query_pool.submit(Ledger(ledger_index="validated"))

                if query_result.success and query_result.response is not None:
                    response = query_result.response
                    if response.is_successful():
                        self._last_ledger_index = response.result.get("ledger_index")
                        self._last_recv_time = time.time()
                        self.logger().debug(
                            f"[POLL] Initialized polling from ledger index: {self._last_ledger_index}"
                        )
                        return

            self.logger().warning(
                "[POLL] Failed to get current ledger index"
            )
        except KeyError as e:
            self.logger().warning(f"Request lost during client reconnection: {e}")
        except Exception as e:
            self.logger().warning(
                f"[POLL] Error initializing ledger index: {e}, will process from account history"
            )

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Poll the XRPL ledger for account state changes.

        This method replaces the WebSocket-based subscription with a polling approach
        that periodically queries the account's transaction history.

        :param output: the queue to use to store the received messages
        """
        self.logger().info(
            f"Starting XRPL polling data source for account {self._auth.get_account()}"
        )

        while True:
            try:
                if self._last_ledger_index is None:
                    # Ledger index not initialized yet, wait and try again
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue

                # Poll account state first (don't wait on first iteration)
                events = await self._poll_account_state()

                # Put events in output queue
                for event in events:
                    self._last_recv_time = time.time()
                    output.put_nowait(event)

                # Wait for poll interval after processing
                await asyncio.sleep(self.POLL_INTERVAL)

            except asyncio.CancelledError:
                self.logger().info("Polling data source cancelled")
                raise
            except Exception as e:
                self.logger().error(
                    f"Error polling account state: {e}",
                    exc_info=True
                )
                # Wait before retrying
                await asyncio.sleep(self.POLL_INTERVAL)

    async def _poll_account_state(self) -> List[Dict[str, Any]]:
        """
        Poll the account's transaction history for new transactions.

        Returns:
            List of event messages to process
        """
        events = []

        try:
            # Build AccountTx request
            account = self._auth.get_account()

            # Prepare request parameters
            request_params = {
                "account": account,
                "limit": 50,  # Reasonable limit for recent transactions
                "forward": True,  # Get transactions in chronological order
            }

            # Add ledger index filter if we have a starting point
            if self._last_ledger_index is not None:
                request_params["ledger_index_min"] = self._last_ledger_index

            # Execute query using query pool
            if self._worker_manager is not None:
                # Get query pool from worker manager
                query_pool: XRPLQueryWorkerPool = self._worker_manager.get_query_pool()
                query_result = await query_pool.submit(AccountTx(**request_params))

                if not query_result.success or query_result.response is None:
                    self.logger().warning(f"AccountTx request failed: {query_result.error}")
                    return events

                response = query_result.response
                if not response.is_successful():
                    self.logger().warning(f"AccountTx request failed: {response.result}")
                    return events
                result = response.result
            else:
                # Direct query using node pool (no burst - respect rate limits)
                client = await self._connector._node_pool.get_client(use_burst=False)
                try:
                    response = await client._request_impl(AccountTx(**request_params))
                except KeyError as e:
                    # KeyError can occur if the connection reconnects during the request,
                    # which clears _open_requests in the XRPL library
                    self.logger().warning(f"Request lost during client reconnection: {e}")
                    return events  # Return empty events, will retry on next poll
                if response.is_successful():
                    result = response.result
                else:
                    self.logger().warning(f"AccountTx request failed: {response.result}")
                    return events

            # Process transactions
            transactions = result.get("transactions", [])

            # Debug logging: Log all transactions received from AccountTx
            if len(transactions) > 0:
                self.logger().debug(
                    f"[POLL_DEBUG] AccountTx returned {len(transactions)} txs (ledger_min={self._last_ledger_index})"
                )
                for i, tx_data in enumerate(transactions):
                    tx_temp = tx_data.get("tx") or tx_data.get("tx_json") or tx_data.get("transaction") or {}
                    tx_hash_temp = tx_temp.get("hash") or tx_data.get("hash")
                    tx_ledger_temp = tx_temp.get("ledger_index") or tx_data.get("ledger_index")
                    tx_type_temp = tx_temp.get("TransactionType")
                    tx_seq_temp = tx_temp.get("Sequence")
                    self.logger().debug(
                        f"[POLL_DEBUG] TX[{i}]: {tx_hash_temp}, ledger={tx_ledger_temp}, "
                        f"type={tx_type_temp}, seq={tx_seq_temp}"
                    )

            for tx_data in transactions:
                # Get transaction and metadata
                tx = tx_data.get("tx") or tx_data.get("tx_json") or tx_data.get("transaction")
                meta = tx_data.get("meta")

                if tx is None or meta is None:
                    continue

                # Check for duplicates
                tx_hash = tx.get("hash") or tx_data.get("hash")
                if tx_hash and self._is_duplicate(tx_hash):
                    self.logger().debug(f"[POLL_DEBUG] Skipping duplicate: {tx_hash}")
                    continue

                # Update ledger index tracking
                ledger_index = tx.get("ledger_index") or tx_data.get("ledger_index")
                if ledger_index is not None:
                    if self._last_ledger_index is None or ledger_index > self._last_ledger_index:
                        self.logger().debug(
                            f"[POLL_DEBUG] Updating last_ledger_index: {self._last_ledger_index} -> {ledger_index}"
                        )
                        self._last_ledger_index = ledger_index

                # Transform to event format
                event = self._transform_to_event(tx, meta, tx_data)
                if event is not None:
                    self.logger().debug(f"[POLL_DEBUG] Event created: {tx_hash}, ledger={ledger_index}")
                    events.append(event)

            self.logger().debug(
                f"Polled {len(transactions)} transactions, {len(events)} new events"
            )

        except Exception as e:
            self.logger().error(f"Error in _poll_account_state: {e}")

        return events

    def _is_duplicate(self, tx_hash: str) -> bool:
        """
        Check if a transaction has already been processed.

        Args:
            tx_hash: The transaction hash to check

        Returns:
            True if the transaction is a duplicate
        """
        if tx_hash in self._seen_tx_hashes_set:
            return True

        # Add to both queue (for FIFO ordering) and set (for O(1) lookup)
        self._seen_tx_hashes_queue.append(tx_hash)
        self._seen_tx_hashes_set.add(tx_hash)

        # Prune if too large (FIFO - oldest entries removed first)
        while len(self._seen_tx_hashes_queue) > self._seen_tx_hashes_max_size:
            oldest_hash = self._seen_tx_hashes_queue.popleft()
            self._seen_tx_hashes_set.discard(oldest_hash)

        return False

    def _transform_to_event(
        self,
        tx: Dict[str, Any],
        meta: Dict[str, Any],
        tx_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Transform an XRPL transaction into an internal event format.

        Args:
            tx: The transaction object
            meta: The transaction metadata
            tx_data: The full transaction data

        Returns:
            An event message or None if the transaction should be ignored
        """
        tx_type = tx.get("TransactionType")

        # Only process relevant transaction types
        if tx_type not in ["OfferCreate", "OfferCancel", "Payment"]:
            return None

        # Check if transaction was successful
        tx_result = meta.get("TransactionResult", "")
        if not tx_result.startswith("tes"):
            # Transaction failed, but might still be relevant for order tracking
            pass

        # Build event message in format expected by _user_stream_event_listener
        event = {
            "transaction": tx,
            "tx": tx,
            "meta": meta,
            "hash": tx.get("hash") or tx_data.get("hash"),
            "ledger_index": tx.get("ledger_index") or tx_data.get("ledger_index"),
            "validated": tx_data.get("validated", True),
        }

        return event

    def set_worker_manager(self, worker_manager: XRPLWorkerPoolManager):
        """
        Set the worker manager for executing queries.

        Args:
            worker_manager: The worker pool manager
        """
        self._worker_manager = worker_manager

    def reset_state(self):
        """Reset the polling state (useful for reconnection scenarios)."""
        self._last_ledger_index = None
        self._seen_tx_hashes_queue.clear()
        self._seen_tx_hashes_set.clear()
        self.logger().info("Polling data source state reset")
