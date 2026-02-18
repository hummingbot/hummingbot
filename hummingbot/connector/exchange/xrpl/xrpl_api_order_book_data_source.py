import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

# XRPL imports
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import BookOffers, Subscribe, SubscribeBook
from xrpl.utils import get_order_book_changes, ripple_time_to_posix

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_order_book import XRPLOrderBook
from hummingbot.connector.exchange.xrpl.xrpl_worker_manager import XRPLWorkerPoolManager
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import XRPLQueryWorkerPool
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


@dataclass
class SubscriptionConnection:
    """
    Represents a dedicated WebSocket connection for order book subscriptions.

    These connections are NOT part of the shared node pool - they are dedicated
    to receiving streaming subscription messages for a specific trading pair.
    """
    trading_pair: str
    url: str
    client: Optional[AsyncWebsocketClient] = None
    listener_task: Optional[asyncio.Task] = None
    is_connected: bool = False
    reconnect_count: int = 0
    last_message_time: float = field(default_factory=time.time)

    def update_last_message_time(self):
        """Update the last message timestamp."""
        self.last_message_time = time.time()

    def is_stale(self, timeout: float) -> bool:
        """Check if the connection hasn't received messages recently."""
        return (time.time() - self.last_message_time) > timeout


class XRPLAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    last_parsed_trade_timestamp: Dict[str, int] = {}
    last_parsed_order_book_timestamp: Dict[str, int] = {}

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "XrplExchange",
        api_factory: WebAssistantsFactory,
        worker_manager: Optional[XRPLWorkerPoolManager] = None,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._worker_manager = worker_manager

        # Message queue keys
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_EVENT_TYPE

        # Subscription connections (dedicated, NOT from shared pool)
        self._subscription_connections: Dict[str, SubscriptionConnection] = {}
        self._subscription_lock = asyncio.Lock()

        # Node URL rotation for subscriptions (separate from pool's rotation)
        self._subscription_node_index: int = 0

    def set_worker_manager(self, worker_manager: XRPLWorkerPoolManager):
        """
        Set the worker manager for executing queries.

        Args:
            worker_manager: The worker pool manager
        """
        self._worker_manager = worker_manager

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    def _get_next_node_url(self, exclude_url: Optional[str] = None) -> Optional[str]:
        """
        Get the next node URL for subscription, respecting bad node tracking.
        Uses round-robin selection, skipping bad nodes.

        Args:
            exclude_url: Optional URL to exclude (e.g., current failing node)

        Returns:
            A node URL or None if no healthy nodes available
        """
        node_urls = self._connector._node_pool._node_urls
        bad_nodes = self._connector._node_pool._bad_nodes
        current_time = time.time()

        # Try each node in round-robin order
        for _ in range(len(node_urls)):
            url = node_urls[self._subscription_node_index]
            self._subscription_node_index = (self._subscription_node_index + 1) % len(node_urls)

            # Skip excluded URL
            if url == exclude_url:
                continue

            # Skip bad nodes that are still in cooldown
            if url in bad_nodes and bad_nodes[url] > current_time:
                continue

            return url

        # Fallback: return any node if all are bad
        return node_urls[0] if node_urls else None

    async def _create_subscription_connection(
        self,
        trading_pair: str,
        exclude_url: Optional[str] = None,
    ) -> Optional[AsyncWebsocketClient]:
        """
        Create a dedicated WebSocket connection for subscription.

        This connection is NOT from the shared pool - it's dedicated to this subscription
        and will be closed when the subscription ends or fails.

        Args:
            trading_pair: The trading pair this connection is for
            exclude_url: URL to exclude from selection (e.g., just-failed node)

        Returns:
            Connected AsyncWebsocketClient or None if connection failed
        """
        tried_urls: Set[str] = set()
        node_urls = self._connector._node_pool._node_urls

        while len(tried_urls) < len(node_urls):
            url = self._get_next_node_url(exclude_url=exclude_url)
            if url is None or url in tried_urls:
                break

            tried_urls.add(url)

            try:
                client = AsyncWebsocketClient(url)
                await asyncio.wait_for(
                    client.open(),
                    timeout=CONSTANTS.SUBSCRIPTION_CONNECTION_TIMEOUT
                )

                # Configure WebSocket settings
                if client._websocket is not None:
                    client._websocket.max_size = CONSTANTS.WEBSOCKET_MAX_SIZE_BYTES
                    client._websocket.ping_interval = 10
                    client._websocket.ping_timeout = CONSTANTS.WEBSOCKET_CONNECTION_TIMEOUT

                self.logger().debug(
                    f"[SUBSCRIPTION] Created dedicated connection for {trading_pair} to {url}"
                )
                return client

            except asyncio.TimeoutError:
                self.logger().warning(
                    f"[SUBSCRIPTION] Connection timeout for {trading_pair} to {url}"
                )
                self._connector._node_pool.mark_bad_node(url)
            except Exception as e:
                self.logger().warning(
                    f"[SUBSCRIPTION] Failed to connect for {trading_pair} to {url}: {e}"
                )
                self._connector._node_pool.mark_bad_node(url)

        self.logger().error(
            f"[SUBSCRIPTION] Failed to create connection for {trading_pair} after trying {len(tried_urls)} nodes"
        )
        return None

    async def _close_subscription_connection(self, client: Optional[AsyncWebsocketClient]):
        """
        Safely close a subscription connection.

        Args:
            client: The client to close (may be None)
        """
        if client is not None:
            try:
                await client.close()
            except Exception as e:
                self.logger().debug(f"[SUBSCRIPTION] Error closing connection: {e}")

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange using the worker pool.

        :param trading_pair: the trading pair for which the order book will be retrieved
        :return: the response from the exchange (JSON dictionary)
        """
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)

        if self._worker_manager is None:
            raise RuntimeError("Worker manager not initialized for order book data source")

        query_pool: XRPLQueryWorkerPool = self._worker_manager.get_query_pool()

        # Fetch both sides in parallel using query pool
        asks_request = BookOffers(
            ledger_index="current",
            taker_gets=base_currency,
            taker_pays=quote_currency,
            limit=CONSTANTS.ORDER_BOOK_DEPTH,
        )
        bids_request = BookOffers(
            ledger_index="current",
            taker_gets=quote_currency,
            taker_pays=base_currency,
            limit=CONSTANTS.ORDER_BOOK_DEPTH,
        )

        try:
            asks_result, bids_result = await asyncio.gather(
                query_pool.submit(asks_request),
                query_pool.submit(bids_request),
            )
        except Exception as e:
            self.logger().error(f"Error fetching order book snapshot for {trading_pair}: {e}")
            raise

        # Check results
        if not asks_result.success:
            raise ValueError(f"Error fetching asks for {trading_pair}: {asks_result.error}")
        if not bids_result.success:
            raise ValueError(f"Error fetching bids for {trading_pair}: {bids_result.error}")

        asks = asks_result.response.result.get("offers", [])
        bids = bids_result.response.result.get("offers", [])

        if asks is None or bids is None:
            raise ValueError(f"Invalid order book response for {trading_pair}")

        return {"asks": asks, "bids": bids}

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the order snapshot events queue. For each event it creates a snapshot message instance and adds it to the
        output queue.
        This method also request the full order book content from the exchange using HTTP requests if it does not
        receive events during one hour.

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        while True:
            try:
                await self._request_order_book_snapshots(output=output)
                await self._sleep(CONSTANTS.REQUEST_ORDERBOOK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book snapshots from exchange")
                await self._sleep(CONSTANTS.REQUEST_ORDERBOOK_INTERVAL)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()

        snapshot_msg: OrderBookMessage = XRPLOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=snapshot_timestamp,
            metadata={"trading_pair": trading_pair},
        )

        self.last_parsed_order_book_timestamp[trading_pair] = int(snapshot_timestamp)

        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = raw_message["trading_pair"]
        trade = raw_message["trade"]

        msg = {
            "trading_pair": trading_pair,
            "price": trade["price"],
            "amount": trade["amount"],
            "transact_time": trade["update_id"],
            "trade_id": trade["trade_id"],
            "trade_type": trade["trade_type"],
            "timestamp": trade["timestamp"],
        }

        trade_message = XRPLOrderBook.trade_message_from_exchange(msg)
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _process_websocket_messages_for_pair(self, trading_pair: str):
        """
        Process WebSocket subscription messages for a trading pair.

        Uses a DEDICATED connection (not from the shared pool) that is managed
        independently for this subscription.
        """
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)
        account = self._connector.auth.get_account()

        subscribe_book_request = SubscribeBook(
            taker_gets=base_currency,
            taker_pays=quote_currency,
            taker=account,
            snapshot=False,
            both=True,
        )
        subscribe = Subscribe(books=[subscribe_book_request])

        retry_count = 0
        last_url: Optional[str] = None

        while retry_count < CONSTANTS.SUBSCRIPTION_MAX_RETRIES:
            client: Optional[AsyncWebsocketClient] = None
            health_check_task: Optional[asyncio.Task] = None

            try:
                # Create dedicated connection (NOT from shared pool)
                # Exclude the last failed URL to try a different node
                client = await self._create_subscription_connection(
                    trading_pair,
                    exclude_url=last_url if retry_count > 0 else None
                )

                if client is None:
                    raise ConnectionError(f"Failed to create subscription connection for {trading_pair}")

                last_url = client.url

                # Track this connection
                async with self._subscription_lock:
                    self._subscription_connections[trading_pair] = SubscriptionConnection(
                        trading_pair=trading_pair,
                        url=client.url,
                        client=client,
                        is_connected=True,
                    )

                # Subscribe to order book
                await client.send(subscribe)
                self.logger().debug(f"[SUBSCRIPTION] Subscribed to {trading_pair} order book via {client.url}")

                # Start health check task
                health_check_task = asyncio.create_task(
                    self._subscription_health_check(trading_pair)
                )

                # Reset retry count on successful connection
                retry_count = 0

                # Process messages (this blocks until connection closes or error)
                await self._on_message_with_health_tracking(client, trading_pair, base_currency)

            except asyncio.CancelledError:
                self.logger().debug(f"[SUBSCRIPTION] Listener for {trading_pair} cancelled")
                raise
            except (ConnectionError, TimeoutError) as e:
                self.logger().warning(f"[SUBSCRIPTION] Connection error for {trading_pair}: {e}")
                if last_url:
                    self._connector._node_pool.mark_bad_node(last_url)
                retry_count += 1
            except Exception as e:
                self.logger().exception(f"[SUBSCRIPTION] Unexpected error for {trading_pair}: {e}")
                retry_count += 1
            finally:
                # Cancel health check
                if health_check_task is not None:
                    health_check_task.cancel()
                    try:
                        await health_check_task
                    except asyncio.CancelledError:
                        pass

                # Remove from tracking
                async with self._subscription_lock:
                    self._subscription_connections.pop(trading_pair, None)

                # Close the dedicated connection
                await self._close_subscription_connection(client)

                if retry_count < CONSTANTS.SUBSCRIPTION_MAX_RETRIES:
                    self.logger().debug(
                        f"[SUBSCRIPTION] Reconnecting {trading_pair} in {CONSTANTS.SUBSCRIPTION_RECONNECT_DELAY}s "
                        f"(attempt {retry_count + 1}/{CONSTANTS.SUBSCRIPTION_MAX_RETRIES})"
                    )
                    await self._sleep(CONSTANTS.SUBSCRIPTION_RECONNECT_DELAY)

        self.logger().error(
            f"[SUBSCRIPTION] Max retries ({CONSTANTS.SUBSCRIPTION_MAX_RETRIES}) reached for {trading_pair}, "
            f"subscription stopped"
        )

    async def _subscription_health_check(self, trading_pair: str):
        """
        Monitor subscription health and force reconnection if stale.

        Runs as a background task while the subscription is active.
        """
        while True:
            try:
                await asyncio.sleep(CONSTANTS.SUBSCRIPTION_HEALTH_CHECK_INTERVAL)

                async with self._subscription_lock:
                    conn = self._subscription_connections.get(trading_pair)
                    if conn is None:
                        # Subscription ended
                        return

                    if conn.is_stale(CONSTANTS.SUBSCRIPTION_STALE_TIMEOUT):
                        self.logger().warning(
                            f"[SUBSCRIPTION] {trading_pair} is stale "
                            f"(no message for {CONSTANTS.SUBSCRIPTION_STALE_TIMEOUT}s), forcing reconnect"
                        )
                        # Close the client to trigger reconnection
                        if conn.client is not None:
                            await self._close_subscription_connection(conn.client)
                        return

            except asyncio.CancelledError:
                return
            except Exception as e:
                self.logger().debug(f"[SUBSCRIPTION] Health check error for {trading_pair}: {e}")

    async def _on_message_with_health_tracking(
        self,
        client: AsyncWebsocketClient,
        trading_pair: str,
        base_currency
    ):
        """
        Process incoming WebSocket messages and update health tracking.
        """
        async for message in client:
            try:
                # Update last message time for health tracking
                async with self._subscription_lock:
                    conn = self._subscription_connections.get(trading_pair)
                    if conn is not None:
                        conn.update_last_message_time()

                # Process the message
                transaction = message.get("transaction") or message.get("tx_json")
                meta = message.get("meta")

                if transaction is None or meta is None:
                    self.logger().debug(f"Received message without transaction or meta: {message}")
                    continue

                order_book_changes = get_order_book_changes(meta)
                for account_offer_changes in order_book_changes:
                    for offer_change in account_offer_changes["offer_changes"]:
                        if offer_change["status"] in ["partially-filled", "filled"]:
                            taker_gets = offer_change["taker_gets"]
                            taker_gets_currency = taker_gets["currency"]
                            price = float(offer_change["maker_exchange_rate"])
                            filled_quantity = abs(Decimal(offer_change["taker_gets"]["value"]))
                            transact_time = ripple_time_to_posix(transaction["date"])
                            trade_id = transaction["date"] + transaction["Sequence"]
                            timestamp = time.time()

                            if taker_gets_currency == base_currency.currency:
                                trade_type = float(TradeType.BUY.value)
                            else:
                                price = 1 / price
                                trade_type = float(TradeType.SELL.value)

                            trade_data = {
                                "trade_type": trade_type,
                                "trade_id": trade_id,
                                "update_id": transact_time,
                                "price": Decimal(price),
                                "amount": filled_quantity,
                                "timestamp": timestamp,
                            }

                            self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(
                                {"trading_pair": trading_pair, "trade": trade_data}
                            )
                            self.last_parsed_trade_timestamp[trading_pair] = int(timestamp)

            except Exception as e:
                self.logger().exception(f"Error processing order book message: {e}")

    async def listen_for_subscriptions(self):  # type: ignore
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """

        async def handle_subscription(trading_pair):
            while True:
                try:
                    await self._process_websocket_messages_for_pair(trading_pair=trading_pair)
                except asyncio.CancelledError:
                    self.logger().debug(f"[SUBSCRIPTION] Handler for {trading_pair} cancelled")
                    raise
                except ConnectionError as connection_exception:
                    self.logger().warning(
                        f"The websocket connection to {trading_pair} was closed ({connection_exception})"
                    )
                except TimeoutError:
                    self.logger().warning(
                        "Timeout error occurred while listening to order book stream. Retrying..."
                    )
                except Exception:
                    self.logger().exception(
                        "Unexpected error occurred when listening to order book streams. Retrying...",
                    )
                finally:
                    await self._sleep(CONSTANTS.SUBSCRIPTION_RECONNECT_DELAY)

        tasks = [handle_subscription(trading_pair) for trading_pair in self._trading_pairs]

        try:
            await safe_gather(*tasks)
        finally:
            # Cleanup all subscription connections on shutdown
            async with self._subscription_lock:
                for trading_pair, conn in list(self._subscription_connections.items()):
                    await self._close_subscription_connection(conn.client)
                self._subscription_connections.clear()
            self.logger().debug("[SUBSCRIPTION] All subscription connections closed")

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """Dynamic subscription not supported for this connector."""
        self.logger().warning(
            f"Dynamic subscription not supported for {self.__class__.__name__}"
        )
        return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """Dynamic unsubscription not supported for this connector."""
        self.logger().warning(
            f"Dynamic unsubscription not supported for {self.__class__.__name__}"
        )
        return False
