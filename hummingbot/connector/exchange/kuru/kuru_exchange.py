"""
Kuru Exchange connector for Hummingbot.

Wraps the kuru-mm-py SDK to integrate Kuru's on-chain CLOB DEX
with Hummingbot's trading strategies (e.g., pure market making).

Key design: SDK order callbacks are bridged to Hummingbot's order
tracker via an asyncio.Queue, ensuring thread-safe event processing.
"""

import asyncio
import logging
import sys
import time
import types
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import (
    InFlightOrder,
    OrderState,
    OrderUpdate,
    TradeUpdate,
)
from hummingbot.core.data_type.order_book_tracker_data_source import (
    OrderBookTrackerDataSource,
)
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import (
    UserStreamTrackerDataSource,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.web_assistants_factory import (
    WebAssistantsFactory,
)

from kuru_sdk_py.client import KuruClient
from kuru_sdk_py.configs import (
    ConfigManager,
    ConnectionConfig,
    MarketConfig,
    OrderExecutionConfig,
    TransactionConfig,
    WalletConfig,
)
from kuru_sdk_py.feed.orderbook_ws import (
    FrontendOrderbookUpdate,
)
from kuru_sdk_py.manager.order import Order as SdkOrder
from kuru_sdk_py.manager.order import OrderSide as SdkOrderSide
from kuru_sdk_py.manager.order import OrderStatus as SdkOrderStatus
from kuru_sdk_py.manager.order import OrderType as SdkOrderType

from kuru_sdk_py.transaction.nonce_manager import NonceManager
from kuru_sdk_py.utils.errors import decode_contract_error

from hummingbot.connector.exchange.kuru import kuru_constants as CONSTANTS
from hummingbot.connector.exchange.kuru.kuru_api_order_book_data_source import (
    KuruAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.kuru.kuru_api_user_stream_data_source import (
    KuruAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.kuru.kuru_auth import KuruAuth
from hummingbot.connector.exchange.kuru.kuru_utils import get_market_config

logger = logging.getLogger(__name__)

# kuru_sdk_py uses loguru (not stdlib logging). Reconfigure it so only
# WARNING+ messages from the SDK are shown, suppressing the INFO noise.
try:
    from loguru import logger as _loguru_logger
    _loguru_logger.remove()
    _loguru_logger.add(
        sys.stderr,
        level="WARNING",
        filter=lambda record: record["name"].startswith("kuru_sdk_py"),
    )
except Exception:
    pass

s_decimal_NaN = Decimal("nan")


async def _send_transaction_with_gas_buffer(
    self,
    function_call,
    value=0,
    access_list=None,
    gas_price=None,
    local_gas_counts=None,
):
    """Patched _send_transaction that applies gas_buffer_multiplier even without an access list.

    This is a monkey-patch for the SDK's AsyncTransactionSenderMixin._send_transaction
    which only applies gas_buffer_multiplier when an access list is present, causing
    'Gas limit too low' errors in the non-access-list path.
    """
    try:
        nonce = await NonceManager.get_and_increment_nonce(self.w3, self.user_address)
        if gas_price is None:
            gas_price = await self.w3.eth.gas_price

        tx_params = {
            "from": self.user_address,
            "nonce": nonce,
            "value": value,
            "gasPrice": gas_price,
        }

        if access_list:
            tx_params["accessList"] = access_list

        tx = await function_call.build_transaction(tx_params)

        try:
            estimated_gas = await self.w3.eth.estimate_gas(tx)

            if access_list:
                total_storage_slots = sum(
                    len(entry.get("storageKeys", [])) for entry in access_list
                )
                adjusted_gas = estimated_gas - (
                    total_storage_slots * self.transaction_config.gas_adjustment_per_slot
                ) + self.transaction_config.gas_buffer
                # Never go below the baseline buffered estimate; slot-based
                # adjustment can be too aggressive on some RPCs.
                adjusted_gas = max(adjusted_gas, 21_000)
                baseline_gas = int(
                    estimated_gas * self.transaction_config.gas_buffer_multiplier
                )
                adjusted_final_gas = int(
                    adjusted_gas * self.transaction_config.gas_buffer_multiplier
                )
                tx["gas"] = max(baseline_gas, adjusted_final_gas, 21_000)
            else:
                # Apply gas buffer multiplier even without access list.
                # local_gas_counts is accepted for SDK 0.1.11 compatibility,
                # but this connector intentionally keeps remote estimation.
                tx["gas"] = max(
                    int(estimated_gas * self.transaction_config.gas_buffer_multiplier),
                    21_000,
                )
        except Exception as e:
            decoded_error = decode_contract_error(e)
            if decoded_error:
                error_msg = f"Transaction would revert: {decoded_error}"
            else:
                error_msg = f"Transaction would fail: {e}"
            raise ValueError(error_msg)

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"Transaction sent: {tx_hash_hex}")
        return tx_hash_hex

    except ValueError as e:
        await NonceManager.mark_transaction_failed(self.user_address)
        logger.error(f"Transaction validation failed: {e}")
        raise
    except Exception as e:
        await NonceManager.mark_transaction_failed(self.user_address)
        error_str = str(e)
        if "Insufficient funds" in error_str or (
            hasattr(e, "args")
            and isinstance(e.args[0], dict)
            and e.args[0].get("code") == -32003
        ):
            try:
                current_balance = await self.w3.eth.get_balance(self.user_address)
                estimated_gas_cost = tx.get("gas", 0) * tx.get("gasPrice", 0)
                total_required = value + estimated_gas_cost
                raise Exception(
                    f"Insufficient funds: wallet has {current_balance / 1e18:.6f} native tokens but needs "
                    f"{total_required / 1e18:.6f} native tokens ({value / 1e18:.6f} for transfer + "
                    f"{estimated_gas_cost / 1e18:.6f} for gas). Please add more native tokens to your wallet."
                )
            except Exception:
                raise Exception(
                    f"Insufficient funds for transaction. Please ensure your wallet has enough native tokens "
                    f"to cover both the transaction value ({value / 1e18:.6f} tokens) and gas costs."
                )

        decoded_error = decode_contract_error(e)
        if decoded_error:
            error_msg = f"Transaction failed with contract error: {decoded_error}"
            logger.error(error_msg)
            raise Exception(error_msg)
        else:
            logger.error(f"Failed to send transaction: {e}")
            raise Exception(f"Transaction failed: {e}")


class KuruExchange(ExchangePyBase):
    """
    Hummingbot exchange connector for Kuru on-chain CLOB DEX.

    Wraps the Kuru SDK (KuruClient) and bridges its async callback-based
    event system with Hummingbot's order tracker and strategy framework.

    Order flow:
        Strategy -> _place_order() -> KuruClient.place_orders() -> on-chain TX
        on-chain event -> SDK callback -> _sdk_order_event_queue
        -> _user_stream_event_listener() -> _order_tracker updates -> Strategy

    Balance model:
        Uses margin account balances (not wallet balances). Orders lock
        margin: buy orders lock quote, sell orders lock base.
    """

    # ----------------------------------------------------------------
    # Class-level config
    # ----------------------------------------------------------------

    web_utils = None  # Not using REST API throttler

    # SDK Order Status -> Hummingbot OrderState mapping
    _SDK_STATUS_MAP = {
        SdkOrderStatus.ORDER_CREATED: OrderState.PENDING_CREATE,
        SdkOrderStatus.ORDER_SENT: OrderState.PENDING_CREATE,
        SdkOrderStatus.ORDER_PLACED: OrderState.OPEN,
        SdkOrderStatus.ORDER_PARTIALLY_FILLED: OrderState.PARTIALLY_FILLED,
        SdkOrderStatus.ORDER_FULLY_FILLED: OrderState.FILLED,
        SdkOrderStatus.ORDER_CANCELLED: OrderState.CANCELED,
        SdkOrderStatus.ORDER_TIMEOUT: OrderState.FAILED,
        SdkOrderStatus.ORDER_FAILED: OrderState.FAILED,
    }

    def __init__(
        self,
        kuru_private_key: str,
        kuru_market_address: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        balance_asset_limit: Optional[Dict[str, Any]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        kuru_rpc_url: Optional[str] = None,
        kuru_rpc_ws_url: Optional[str] = None,
        kuru_ws_url: Optional[str] = None,
        kuru_api_url: Optional[str] = None,
    ):
        # Validate single-market constraint: each SDK instance supports one market
        if trading_pairs and len(trading_pairs) != 1:
            raise ValueError(
                f"KuruExchange supports exactly one trading pair per instance, "
                f"got {len(trading_pairs)}: {trading_pairs}"
            )

        # Store all custom fields BEFORE super().__init__()
        self._private_key = kuru_private_key
        self._market_address = kuru_market_address
        self._domain_str = domain
        self._trading_required = trading_required
        self._trading_pairs_list = trading_pairs or []

        # Optional endpoint overrides
        self._rpc_url = kuru_rpc_url
        self._rpc_ws_url = kuru_rpc_ws_url
        self._kuru_ws_url = kuru_ws_url
        self._kuru_api_url = kuru_api_url

        # Auth
        self._kuru_auth = KuruAuth(kuru_private_key)

        # SDK components (created in start_network)
        self._client: Optional[KuruClient] = None
        self._market_config: Optional[MarketConfig] = None

        # Shared queues for SDK -> Hummingbot bridge
        self._sdk_order_event_queue: asyncio.Queue[SdkOrder] = asyncio.Queue()
        self._sdk_orderbook_queue: asyncio.Queue[FrontendOrderbookUpdate] = (
            asyncio.Queue()
        )

        # Store event loop reference for thread-safe callbacks from the SDK
        self._event_loop = asyncio.get_event_loop()

        # Last traded price cache (updated from orderbook WS events)
        self._last_traded_prices: Dict[str, float] = {}

        # Track SDK start task and health monitor
        self._sdk_start_task: Optional[asyncio.Task] = None
        self._sdk_health_task: Optional[asyncio.Task] = None
        self._cancel_all_orders_task: Optional[asyncio.Task] = None
        self._cancel_all_orders_lock = asyncio.Lock()

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    # ----------------------------------------------------------------
    # Abstract properties
    # ----------------------------------------------------------------

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self):
        return self._kuru_auth

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain_str

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.CLIENT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return ""  # Not used - rules come from SDK MarketConfig

    @property
    def trading_pairs_request_path(self) -> str:
        return ""  # Not used

    @property
    def check_network_request_path(self) -> str:
        return ""  # Not used - we override check_network()

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs_list

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        # Cancel is an on-chain TX - confirmed asynchronously via callback
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    # ----------------------------------------------------------------
    # Public accessors for data sources
    # ----------------------------------------------------------------

    @property
    def sdk_orderbook_queue(self) -> asyncio.Queue:
        """Queue of FrontendOrderbookUpdate for the orderbook data source."""
        return self._sdk_orderbook_queue

    @property
    def last_traded_prices(self) -> Dict[str, float]:
        return self._last_traded_prices

    @property
    def size_precision(self) -> int:
        """Market's size_precision for WS size conversion."""
        if self._market_config:
            return self._market_config.size_precision
        return 1

    # ----------------------------------------------------------------
    # Supported order types
    # ----------------------------------------------------------------

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    # ----------------------------------------------------------------
    # Lifecycle: start / stop / check_network
    # ----------------------------------------------------------------

    async def start_network(self):
        logger.info("start_network() called — launching SDK initialization...")
        await super().start_network()
        self._sdk_start_task = asyncio.ensure_future(self._start_sdk())

    async def stop_network(self):
        logger.info("stop_network() called — tearing down SDK...")
        if self._sdk_health_task is not None:
            self._sdk_health_task.cancel()
            self._sdk_health_task = None
            logger.debug("SDK health monitor task cancelled")

        if self._sdk_start_task is not None:
            self._sdk_start_task.cancel()
            self._sdk_start_task = None
            logger.debug("SDK start task cancelled")

        if self._client is not None:
            try:
                if len(self._order_tracker.active_orders) > 0:
                    logger.info(
                        "stop_network: active tracked orders detected; "
                        "running market-wide cancel fallback"
                    )
                    await self._cancel_all_active_orders_for_market(
                        reason="stop_network with active tracked orders"
                    )
                await self._client.stop()
                logger.info("KuruClient stopped successfully")
            except Exception:
                logger.exception("Error stopping KuruClient")
            self._client = None

        await super().stop_network()
        logger.info("stop_network() complete")

    async def check_network(self) -> NetworkStatus:
        try:
            if self._client is not None:
                # SDK is running — use its health check
                if self._client.is_healthy():
                    logger.debug("check_network: CONNECTED")
                    return NetworkStatus.CONNECTED
                logger.warning("check_network: client reports unhealthy -> NOT_CONNECTED")
                return NetworkStatus.NOT_CONNECTED

            # SDK not yet initialized — do a lightweight reachability check
            # so that start_network() gets triggered
            import aiohttp
            api_url = self._kuru_api_url or CONSTANTS.DEFAULT_KURU_API_URL
            health_url = f"{api_url.rstrip('/')}/healthz"
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        logger.debug("check_network: pre-SDK reachability check -> CONNECTED")
                        return NetworkStatus.CONNECTED
            logger.debug("check_network: pre-SDK reachability check failed -> NOT_CONNECTED")
            return NetworkStatus.NOT_CONNECTED
        except Exception:
            logger.exception("check_network: exception -> NOT_CONNECTED")
            return NetworkStatus.NOT_CONNECTED

    async def _start_sdk(self, max_retries: int = 3):
        """Initialize the Kuru SDK client and connect to all services.

        Retries up to ``max_retries`` times with exponential backoff on failure.
        After successful init, starts the background health monitor.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"_start_sdk: attempt {attempt}/{max_retries} — "
                    f"loading market config for {self._market_address}"
                )
                # Load market config (checks known markets, falls back to chain)
                self._market_config = get_market_config(
                    self._market_address,
                    rpc_url=self._rpc_url,
                )
                logger.info(
                    f"Loaded market config: {self._market_config.market_symbol} "
                    f"(price_precision={self._market_config.price_precision}, "
                    f"size_precision={self._market_config.size_precision}, "
                    f"tick_size={self._market_config.tick_size}, "
                    f"base={self._market_config.base_symbol}[{self._market_config.base_token_decimals}d], "
                    f"quote={self._market_config.quote_symbol}[{self._market_config.quote_token_decimals}d])"
                )

                # Build SDK configs
                wallet_config = self._kuru_auth.get_wallet_config()
                rpc_url = self._rpc_url or CONSTANTS.DEFAULT_RPC_URL
                rpc_ws_url = self._rpc_ws_url or CONSTANTS.DEFAULT_RPC_WS_URL
                kuru_ws_url = self._kuru_ws_url or CONSTANTS.DEFAULT_KURU_WS_URL
                kuru_api_url = self._kuru_api_url or CONSTANTS.DEFAULT_KURU_API_URL
                connection_config = ConnectionConfig(
                    rpc_url=rpc_url,
                    rpc_ws_url=rpc_ws_url,
                    kuru_ws_url=kuru_ws_url,
                    kuru_api_url=kuru_api_url,
                )
                logger.info(
                    f"_start_sdk: connection config — rpc={rpc_url}, "
                    f"rpc_ws={rpc_ws_url}, kuru_ws={kuru_ws_url}, kuru_api={kuru_api_url}"
                )
                logger.info(f"_start_sdk: wallet address={self._kuru_auth.address}")

                # Create SDK client
                logger.info("_start_sdk: creating KuruClient...")
                self._client = await KuruClient.create(
                    market_config=self._market_config,
                    connection_config=connection_config,
                    wallet_config=wallet_config,
                    transaction_config=TransactionConfig(gas_buffer_multiplier=1.5),
                    order_execution_config=OrderExecutionConfig(use_access_list=False),
                )
                logger.info("_start_sdk: KuruClient created successfully")

                # Monkey-patch _send_transaction on executor and user to apply
                # gas_buffer_multiplier even without an access list (SDK bug workaround)
                self._client.executor._send_transaction = types.MethodType(
                    _send_transaction_with_gas_buffer, self._client.executor
                )
                self._client.user._send_transaction = types.MethodType(
                    _send_transaction_with_gas_buffer, self._client.user
                )

                # Register callbacks BEFORE start
                self._client.set_order_callback(self._on_sdk_order_event)
                self._client.set_orderbook_callback(self._on_sdk_orderbook_event)
                logger.debug("_start_sdk: order and orderbook callbacks registered")

                # Start client (EIP-7702 auth, RPC WebSocket, event processing)
                logger.info("_start_sdk: starting KuruClient (EIP-7702 auth, WS connections)...")
                await self._client.start()
                logger.info("_start_sdk: KuruClient started")

                # Subscribe to orderbook WebSocket
                logger.info("_start_sdk: subscribing to orderbook WebSocket...")
                await self._client.subscribe_to_orderbook()
                logger.info("_start_sdk: orderbook WebSocket subscribed")

                # Build initial trading rules
                await self._update_trading_rules()
                logger.info(
                    f"_start_sdk: trading rules built — {dict(self._trading_rules)}"
                )
                await self._cancel_orders_without_kuru_mapping_on_startup()

                # Start health monitor
                self._sdk_health_task = asyncio.ensure_future(self._sdk_health_monitor_loop())

                logger.info("Kuru SDK started successfully — connector is ready")
                return  # success

            except asyncio.CancelledError:
                logger.warning("_start_sdk: cancelled")
                raise
            except Exception as e:
                last_exception = e
                logger.exception(
                    f"_start_sdk: attempt {attempt}/{max_retries} failed"
                )
                # Clean up partial init before retry
                if self._client is not None:
                    try:
                        await self._client.stop()
                    except Exception:
                        pass
                    self._client = None

                if attempt < max_retries:
                    backoff = 2 ** attempt
                    logger.info(f"_start_sdk: retrying in {backoff}s...")
                    await asyncio.sleep(backoff)

        # All retries exhausted
        logger.error(f"_start_sdk: all {max_retries} attempts failed")
        raise last_exception  # type: ignore[misc]

    async def _sdk_health_monitor_loop(self):
        """Periodically check SDK health and restart if unhealthy."""
        while True:
            try:
                await asyncio.sleep(30)
                if self._client is not None and not self._client.is_healthy():
                    logger.warning(
                        "_sdk_health_monitor_loop: SDK is unhealthy — triggering restart"
                    )
                    await self._restart_sdk()
                self._expire_ghost_orders()
            except asyncio.CancelledError:
                logger.info("_sdk_health_monitor_loop: cancelled")
                raise
            except Exception:
                logger.exception("_sdk_health_monitor_loop: error during health check")
                await asyncio.sleep(5)

    def _expire_ghost_orders(self):
        """Mark orders without a kuru_order_id as FAILED after GHOST_ORDER_TIMEOUT_S.

        A "ghost" order is one where the SDK never delivered an ORDER_PLACED
        callback, so it has no kuru_order_id. These orders lock balance forever
        and can never be cancelled individually. This method is called every
        ~30s from the health monitor loop.
        """
        if self._client is None:
            return

        now = time.time()
        for client_order_id, order in list(self._order_tracker.active_orders.items()):
            if order.is_done:
                continue
            kuru_order_id = self._client.orders_manager.get_kuru_order_id(client_order_id)
            if kuru_order_id is not None:
                continue
            age = now - order.creation_timestamp
            if age <= CONSTANTS.GHOST_ORDER_TIMEOUT_S:
                continue

            logger.warning(
                f"Ghost order expired: cloid={client_order_id}, age={age:.0f}s "
                f"(timeout={CONSTANTS.GHOST_ORDER_TIMEOUT_S}s). Marking as FAILED."
            )
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=order.trading_pair,
                    update_timestamp=now,
                    new_state=OrderState.FAILED,
                    client_order_id=client_order_id,
                    exchange_order_id=order.exchange_order_id,
                )
            )

    async def _restart_sdk(self):
        """Gracefully stop and re-initialize the SDK."""
        logger.info("_restart_sdk: stopping current SDK client...")
        if self._client is not None:
            try:
                await self._client.stop()
            except Exception:
                logger.exception("_restart_sdk: error stopping client")
            self._client = None

        logger.info("_restart_sdk: re-initializing SDK...")
        await self._start_sdk()

    # ----------------------------------------------------------------
    # SDK callbacks
    # ----------------------------------------------------------------

    async def _on_sdk_order_event(self, sdk_order: SdkOrder):
        """SDK order callback -> push to bridge queue (non-blocking, thread-safe)."""
        logger.info(
            f"SDK order event: cloid={sdk_order.cloid}, type={sdk_order.order_type}, "
            f"status={sdk_order.status}, side={getattr(sdk_order, 'side', '?')}, "
            f"price={getattr(sdk_order, 'price', '?')}, size={getattr(sdk_order, 'size', '?')}, "
            f"kuru_order_id={sdk_order.kuru_order_id}, "
            f"filled_sizes={getattr(sdk_order, 'filled_sizes', [])}"
        )
        try:
            self._sdk_order_event_queue.put_nowait(sdk_order)
        except Exception:
            logger.exception(f"Failed to enqueue SDK order event for cloid={sdk_order.cloid}")

    async def _on_sdk_orderbook_event(self, update: FrontendOrderbookUpdate):
        """SDK orderbook callback -> update last traded price + push to queue (non-blocking)."""
        num_bids = len(update.b) if update.b else 0
        num_asks = len(update.a) if update.a else 0
        event_types = [e.e for e in update.events] if update.events else []
        logger.debug(
            f"SDK orderbook event: bids={num_bids}, asks={num_asks}, "
            f"events={event_types}"
        )

        # Extract last traded price from trade events. SDK frontend updates are
        # normalized by default in 0.1.11, so store plain floats for Hummingbot.
        for event in update.events:
            if event.e == "Trade" and event.p is not None:
                last_price = float(event.p)
                for pair in self._trading_pairs_list:
                    self._last_traded_prices[pair] = last_price
                    logger.info(f"Last traded price updated: {pair}={last_price}")

        try:
            self._sdk_orderbook_queue.put_nowait(update)
        except Exception:
            logger.exception("Failed to enqueue SDK orderbook event")

    # ----------------------------------------------------------------
    # User stream event listener (SDK callback bridge)
    # ----------------------------------------------------------------

    async def _user_stream_event_listener(self):
        """
        Consume SDK order events from the bridge queue and map them
        to Hummingbot OrderUpdate / TradeUpdate for the order tracker.
        """
        logger.info("_user_stream_event_listener: started, waiting for SDK order events...")
        while True:
            try:
                sdk_order: SdkOrder = await self._sdk_order_event_queue.get()
                logger.debug(
                    f"_user_stream_event_listener: dequeued event for cloid={sdk_order.cloid}, "
                    f"status={sdk_order.status}"
                )
                await self._process_sdk_order_event(sdk_order)
            except asyncio.CancelledError:
                logger.info("_user_stream_event_listener: cancelled")
                raise
            except Exception:
                logger.exception("Error in SDK order event listener")
                await asyncio.sleep(1.0)

    async def _process_sdk_order_event(self, sdk_order: SdkOrder):
        """Process a single SDK Order event."""
        client_order_id = sdk_order.cloid

        # Skip cancel-type orders (cancel confirmations come via original order)
        if sdk_order.order_type == SdkOrderType.CANCEL:
            logger.debug(f"_process_sdk_order_event: skipping CANCEL-type event for cloid={client_order_id}")
            return

        # Find the tracked order in Hummingbot
        tracked_order = self._order_tracker.fetch_order(
            client_order_id=client_order_id
        )
        if tracked_order is None:
            logger.warning(
                f"_process_sdk_order_event: no tracked order found for cloid={client_order_id} "
                f"(status={sdk_order.status}) — event ignored"
            )
            return

        status = sdk_order.status
        logger.info(
            f"_process_sdk_order_event: cloid={client_order_id}, sdk_status={status}, "
            f"tracked_state={tracked_order.current_state}, "
            f"exchange_order_id={tracked_order.exchange_order_id}"
        )

        if status == SdkOrderStatus.ORDER_PLACED:
            # Order confirmed on-chain - update to real exchange_order_id
            exchange_order_id = (
                str(sdk_order.kuru_order_id)
                if sdk_order.kuru_order_id is not None
                else None
            )
            logger.info(
                f"Order PLACED on-chain: cloid={client_order_id}, "
                f"kuru_order_id={exchange_order_id}"
            )
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.OPEN,
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                )
            )

        elif status in (
            SdkOrderStatus.ORDER_PARTIALLY_FILLED,
            SdkOrderStatus.ORDER_FULLY_FILLED,
        ):
            # Process any new fills
            logger.info(
                f"Order FILL: cloid={client_order_id}, status={status}, "
                f"filled_sizes={getattr(sdk_order, 'filled_sizes', [])}"
            )
            self._process_fills(sdk_order, tracked_order)

            new_state = (
                OrderState.PARTIALLY_FILLED
                if status == SdkOrderStatus.ORDER_PARTIALLY_FILLED
                else OrderState.FILLED
            )
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=new_state,
                    client_order_id=client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
            )

        elif status == SdkOrderStatus.ORDER_CANCELLED:
            logger.info(f"Order CANCELLED: cloid={client_order_id}")
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.CANCELED,
                    client_order_id=client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
            )

        elif status == SdkOrderStatus.ORDER_TIMEOUT:
            logger.warning(f"Order TIMEOUT: cloid={client_order_id}")
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.FAILED,
                    client_order_id=client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
            )

        elif status == SdkOrderStatus.ORDER_FAILED:
            logger.error(f"Order FAILED: cloid={client_order_id}")
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.FAILED,
                    client_order_id=client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
            )

        else:
            logger.debug(
                f"_process_sdk_order_event: unhandled status={status} for cloid={client_order_id}"
            )

    def _process_fills(self, sdk_order: SdkOrder, tracked_order: InFlightOrder):
        """
        Emit TradeUpdate for each new fill in the SDK order.

        Compares the number of fills already reported to Hummingbot
        (len(tracked_order.order_fills)) against the SDK's fill list
        (sdk_order.filled_sizes) and reports only new ones.
        """
        already_reported = len(tracked_order.order_fills)
        all_fills = sdk_order.filled_sizes

        exchange_order_id = (
            str(sdk_order.kuru_order_id)
            if sdk_order.kuru_order_id is not None
            else tracked_order.exchange_order_id
        )

        logger.debug(
            f"_process_fills: cloid={sdk_order.cloid}, already_reported={already_reported}, "
            f"total_fills={len(all_fills)}, new_fills={len(all_fills) - already_reported}"
        )

        for i in range(already_reported, len(all_fills)):
            fill_size = Decimal(str(all_fills[i]))
            # Maker fills execute at the limit price
            fill_price = tracked_order.price if tracked_order.price else Decimal("0")
            fill_quote = fill_price * fill_size

            fee = AddedToCostTradeFee(
                percent=Decimal("0"),  # Maker fee is 0%
            )

            trade_update = TradeUpdate(
                trade_id=f"{sdk_order.cloid}_{i}",
                client_order_id=sdk_order.cloid,
                exchange_order_id=exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=time.time(),
                fill_price=fill_price,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_quote,
                fee=fee,
                is_taker=False,
            )
            logger.info(
                f"Trade fill #{i}: cloid={sdk_order.cloid}, price={fill_price}, "
                f"size={fill_size}, quote={fill_quote}"
            )
            self._order_tracker.process_trade_update(trade_update)

    # ----------------------------------------------------------------
    # Order placement
    # ----------------------------------------------------------------

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        """
        Place a single limit order on Kuru via the SDK.

        Returns (txhash, timestamp). The txhash serves as a temporary
        exchange_order_id until the real kuru_order_id arrives via callback.
        """
        if self._client is None:
            raise RuntimeError("KuruClient not initialized - call start_network first")

        side = SdkOrderSide.BUY if trade_type == TradeType.BUY else SdkOrderSide.SELL

        logger.info(
            f"_place_order: cloid={order_id}, pair={trading_pair}, "
            f"side={side}, type={order_type}, price={price}, amount={amount}"
        )

        sdk_order = SdkOrder(
            cloid=order_id,
            order_type=SdkOrderType.LIMIT,
            side=side,
            price=float(price),
            size=float(amount),
            post_only=True,
        )

        txhash = await self._client.place_orders([sdk_order])
        logger.info(f"_place_order: order submitted, txhash={txhash}, cloid={order_id}")
        return txhash, time.time()

    # ----------------------------------------------------------------
    # Order cancellation
    # ----------------------------------------------------------------

    async def _cancel_all_active_orders_for_market(self, reason: str) -> bool:
        """
        Fallback cancel path for startup/shutdown and missing cloid mapping.

        Uses SDK market-wide cancellation and de-duplicates concurrent calls.
        """
        if self._client is None:
            logger.warning("Cannot cancel all active orders: KuruClient not initialized")
            return False

        async with self._cancel_all_orders_lock:
            if (
                self._cancel_all_orders_task is None
                or self._cancel_all_orders_task.done()
            ):
                logger.warning(
                    "_cancel_all_active_orders_for_market: invoking SDK cancel-all "
                    f"(reason={reason})"
                )
                self._cancel_all_orders_task = asyncio.create_task(
                    self._client.cancel_all_active_orders_for_market()
                )
            else:
                logger.info(
                    "_cancel_all_active_orders_for_market: cancel-all already running "
                    f"(reason={reason})"
                )
            cancel_task = self._cancel_all_orders_task

        try:
            await cancel_task
            self._mark_ghost_orders_failed()
            logger.info("_cancel_all_active_orders_for_market: completed")
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("_cancel_all_active_orders_for_market: failed")
            return False
        finally:
            async with self._cancel_all_orders_lock:
                if (
                    self._cancel_all_orders_task is cancel_task
                    and cancel_task.done()
                ):
                    self._cancel_all_orders_task = None

    async def _cancel_orders_without_kuru_mapping_on_startup(self):
        """
        On bot restart, tracked orders can exist without cloid->kuru_order_id mapping.
        In that case, fall back to market-wide cancellation.
        """
        if self._client is None:
            return

        active_order_ids = list(self._order_tracker.active_orders.keys())
        if len(active_order_ids) == 0:
            return

        missing_mapping_ids = [
            client_order_id
            for client_order_id in active_order_ids
            if self._client.orders_manager.get_kuru_order_id(client_order_id) is None
        ]
        if len(missing_mapping_ids) == 0:
            return

        logger.warning(
            "_start_sdk: found active tracked orders without cloid->kuru_order_id "
            "mapping; running market-wide cancel fallback "
            f"(count={len(missing_mapping_ids)})"
        )
        await self._cancel_all_active_orders_for_market(
            reason="startup missing cloid->kuru_order_id mapping"
        )

    def _mark_ghost_orders_failed(self):
        """Mark all tracked orders without a kuru_order_id as FAILED.

        Called after a successful market-wide cancel-all. If cancel-all
        succeeded on-chain, any order without a kuru_order_id cannot
        exist on the order book, so it is safe to clean up.
        """
        if self._client is None:
            return

        now = time.time()
        for client_order_id, order in list(self._order_tracker.active_orders.items()):
            if order.is_done:
                continue
            kuru_order_id = self._client.orders_manager.get_kuru_order_id(client_order_id)
            if kuru_order_id is not None:
                continue

            logger.info(
                f"Post-cancel-all cleanup: marking ghost order cloid={client_order_id} "
                f"as FAILED (no kuru_order_id)."
            )
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=order.trading_pair,
                    update_timestamp=now,
                    new_state=OrderState.FAILED,
                    client_order_id=client_order_id,
                    exchange_order_id=order.exchange_order_id,
                )
            )

    async def _place_cancel(
        self, order_id: str, tracked_order: InFlightOrder
    ):
        """
        Cancel an order on Kuru via the SDK.

        Returns True if cancel TX was submitted, False if the order
        hasn't been confirmed on-chain yet (kuru_order_id unknown).
        """
        if self._client is None:
            logger.warning("Cannot cancel: KuruClient not initialized")
            return False

        # Don't cancel already-filled or terminal orders
        if tracked_order.is_done:
            logger.info(
                f"_place_cancel: skipping cancel for cloid={order_id} — "
                f"order already in terminal state ({tracked_order.current_state})"
            )
            return True

        logger.info(f"_place_cancel: attempting to cancel cloid={order_id}")
        kuru_order_id = self._client.orders_manager.get_kuru_order_id(order_id)
        if kuru_order_id is None:
            logger.warning(
                f"Cannot cancel {order_id}: kuru_order_id not yet available "
                "(order may not be confirmed on-chain yet). "
                "Falling back to market-wide cancel."
            )
            return await self._cancel_all_active_orders_for_market(
                reason=f"missing cloid->kuru_order_id mapping for {order_id}"
            )

        logger.info(f"_place_cancel: cloid={order_id} -> kuru_order_id={kuru_order_id}")
        cancel_order = SdkOrder(
            cloid=order_id,
            order_type=SdkOrderType.CANCEL,
            order_ids_to_cancel=[kuru_order_id],
        )

        try:
            await self._client.place_orders([cancel_order])
            logger.info(f"_place_cancel: cancel TX submitted for cloid={order_id}")
            return True
        except Exception:
            logger.exception(f"Failed to cancel order {order_id}")
            return False

    # ----------------------------------------------------------------
    # Balance management
    # ----------------------------------------------------------------

    async def _update_balances(self):
        """
        Fetch margin account balances and compute available balances.

        Available = margin balance - locked in open orders.
        Buy orders lock quote tokens, sell orders lock base tokens.
        """
        if self._client is None or self._market_config is None:
            logger.debug("_update_balances: skipped (client or market_config is None)")
            return

        if not self._trading_pairs_list:
            logger.debug("_update_balances: skipped (no trading pairs configured)")
            return

        try:
            base_margin_wei, quote_margin_wei = (
                await self._client.user.get_margin_balances()
            )
        except Exception:
            logger.exception("Failed to fetch margin balances")
            return

        mc = self._market_config
        # Use the trading pair token names (e.g., "MON", "USDC" from "MON-USDC")
        # rather than market config symbols (e.g., "AUSD") so that balance
        # lookups from the strategy match correctly.
        trading_pair = self._trading_pairs_list[0]
        base_symbol, quote_symbol = trading_pair.split("-")

        base_total = Decimal(str(base_margin_wei)) / Decimal(
            10 ** mc.base_token_decimals
        )
        quote_total = Decimal(str(quote_margin_wei)) / Decimal(
            10 ** mc.quote_token_decimals
        )

        # Compute locked amounts from active orders
        locked_base = Decimal("0")
        locked_quote = Decimal("0")
        active_order_count = len(self._order_tracker.active_orders)
        for order in self._order_tracker.active_orders.values():
            remaining = order.amount - order.executed_amount_base
            if remaining <= Decimal("0"):
                continue
            if order.trade_type == TradeType.BUY:
                order_price = order.price if order.price else Decimal("0")
                locked_quote += order_price * remaining
            else:
                locked_base += remaining

        self._account_balances[base_symbol] = base_total
        self._account_balances[quote_symbol] = quote_total
        self._account_available_balances[base_symbol] = max(
            Decimal("0"), base_total - locked_base
        )
        self._account_available_balances[quote_symbol] = max(
            Decimal("0"), quote_total - locked_quote
        )

        logger.info(
            f"Balances updated: {base_symbol}={base_total} (avail={base_total - locked_base}), "
            f"{quote_symbol}={quote_total} (avail={quote_total - locked_quote}), "
            f"active_orders={active_order_count}, locked_base={locked_base}, locked_quote={locked_quote}"
        )

    # ----------------------------------------------------------------
    # Trading rules
    # ----------------------------------------------------------------

    async def _update_trading_rules(self):
        """Build trading rules from the SDK's MarketConfig."""
        if self._market_config is None:
            logger.debug("_update_trading_rules: skipped (market_config is None)")
            return

        mc = self._market_config
        trading_pair = self._trading_pairs_list[0]
        base_asset, quote_asset = trading_pair.split("-")

        min_price_increment = Decimal(str(mc.tick_size)) / Decimal(
            str(mc.price_precision)
        )
        min_base_amount_increment = Decimal("1") / Decimal(str(mc.size_precision))

        rule = TradingRule(
            trading_pair=trading_pair,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
            supports_limit_orders=True,
            supports_market_orders=False,
            buy_order_collateral_token=quote_asset,
            sell_order_collateral_token=base_asset,
        )
        self._trading_rules.clear()
        self._trading_rules[trading_pair] = rule

        # Ensure the trading pair symbol map is initialized (required for ready status)
        if not self.trading_pair_symbol_map_ready():
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info={})

    async def _format_trading_rules(
        self, exchange_info_dict: Dict[str, Any]
    ) -> List[TradingRule]:
        """
        Parse trading rules from exchange info.

        Called by the base class polling loop. We override
        _update_trading_rules to build rules from MarketConfig
        directly, so this is a passthrough.
        """
        # If market config is available, build from it
        if self._market_config is not None:
            await self._update_trading_rules()
        return list(self._trading_rules.values())

    # ----------------------------------------------------------------
    # Fees
    # ----------------------------------------------------------------

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
        """
        Return trade fee estimate.

        Kuru maker orders (post-only) have 0% fee.
        Taker orders have ~10 bps fee (for estimation).
        """
        is_maker = is_maker or order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER)
        if is_maker:
            return AddedToCostTradeFee(percent=Decimal("0"))
        else:
            return AddedToCostTradeFee(
                percent=Decimal(str(CONSTANTS.DEFAULT_TAKER_FEE_BPS)) / Decimal("10000")
            )

    async def _update_trading_fees(self):
        """No dynamic fee updates needed for on-chain DEX."""
        pass

    # ----------------------------------------------------------------
    # Last traded price
    # ----------------------------------------------------------------

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """Return last traded price from orderbook WS events."""
        price = self._last_traded_prices.get(trading_pair, 0.0)
        logger.debug(f"_get_last_traded_price: {trading_pair}={price}")
        return price

    # ----------------------------------------------------------------
    # Order status queries (REST fallback)
    # ----------------------------------------------------------------

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Query current order status from the SDK's order manager.

        This is a fallback for when events are missed. The primary
        order tracking is via SDK callbacks.
        """
        client_order_id = tracked_order.client_order_id
        sdk_order = self._client.orders_manager.cloid_to_order.get(
            client_order_id
        ) if self._client else None

        if sdk_order is None:
            # Order not found in SDK — if it's older than the ghost timeout,
            # raise so the base class's "order not found" counter (3 strikes)
            # eventually marks it FAILED. For recent orders, return current
            # state unchanged to allow time for the callback to arrive.
            age = time.time() - tracked_order.creation_timestamp
            if age > CONSTANTS.GHOST_ORDER_TIMEOUT_S:
                raise Exception(
                    f"Order {client_order_id} not found in SDK after "
                    f"{age:.0f}s (ghost timeout={CONSTANTS.GHOST_ORDER_TIMEOUT_S}s)"
                )
            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=tracked_order.current_state,
                client_order_id=client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
            )

        new_state = self._SDK_STATUS_MAP.get(
            sdk_order.status, tracked_order.current_state
        )
        exchange_order_id = (
            str(sdk_order.kuru_order_id)
            if sdk_order.kuru_order_id is not None
            else tracked_order.exchange_order_id
        )

        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )

    async def _all_trade_updates_for_order(
        self, order: InFlightOrder
    ) -> List[TradeUpdate]:
        """
        Return all trade fills for an order from the SDK.

        Fallback for missed fill events.
        """
        if self._client is None:
            return []

        sdk_order = self._client.orders_manager.cloid_to_order.get(
            order.client_order_id
        )
        if sdk_order is None:
            return []

        exchange_order_id = (
            str(sdk_order.kuru_order_id)
            if sdk_order.kuru_order_id is not None
            else order.exchange_order_id
        )

        trade_updates = []
        for i, fill_size in enumerate(sdk_order.filled_sizes):
            fill_amount = Decimal(str(fill_size))
            fill_price = order.price if order.price else Decimal("0")

            trade_updates.append(
                TradeUpdate(
                    trade_id=f"{sdk_order.cloid}_{i}",
                    client_order_id=sdk_order.cloid,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fill_timestamp=time.time(),
                    fill_price=fill_price,
                    fill_base_amount=fill_amount,
                    fill_quote_amount=fill_price * fill_amount,
                    fee=AddedToCostTradeFee(percent=Decimal("0")),
                    is_taker=False,
                )
            )
        return trade_updates

    # ----------------------------------------------------------------
    # Network check override
    # ----------------------------------------------------------------

    async def _make_network_check_request(self):
        """Override to check SDK health instead of REST ping."""
        if self._client is None:
            raise ConnectionError("KuruClient not initialized")
        if not self._client.is_healthy():
            raise ConnectionError("KuruClient is not healthy")

    async def _make_trading_rules_request(self) -> Any:
        """Override to return market config data instead of REST call."""
        if self._market_config is not None:
            return {"market_config": self._market_config}
        return {}

    async def _make_trading_pairs_request(self) -> Any:
        """Override to return configured trading pairs."""
        return {"pairs": self._trading_pairs_list}

    # ----------------------------------------------------------------
    # Time synchronization
    # ----------------------------------------------------------------

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        """Override base class to get server time from the RPC instead of web_utils."""
        try:
            await self._time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=self._get_rpc_server_time(),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if not pass_on_non_cancelled_error:
                self.logger().exception("Error requesting time from RPC")
                raise

    async def _get_rpc_server_time(self) -> float:
        """Fetch the latest block timestamp from the RPC and return it in milliseconds."""
        import aiohttp
        rpc_url = self._rpc_url or CONSTANTS.DEFAULT_RPC_URL
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": ["latest", False],
            "id": 1,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                rpc_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                result = await resp.json()
                block_timestamp = int(result["result"]["timestamp"], 16)
                return float(block_timestamp * 1e3)

    # ----------------------------------------------------------------
    # Error classification
    # ----------------------------------------------------------------

    def _is_request_exception_related_to_time_synchronizer(
        self, request_exception: Exception
    ) -> bool:
        # DEX has no server time sync issues
        return False

    def _is_order_not_found_during_status_update_error(
        self, status_update_exception: Exception
    ) -> bool:
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(
        self, cancelation_exception: Exception
    ) -> bool:
        return "not found" in str(cancelation_exception).lower()

    # ----------------------------------------------------------------
    # Factory methods for data sources
    # ----------------------------------------------------------------

    def _create_web_assistants_factory(self) -> Optional[WebAssistantsFactory]:
        """Not used - SDK handles all network communication."""
        return None

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return KuruAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs_list,
            connector=self,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return KuruAPIUserStreamDataSource(connector=self)

    # ----------------------------------------------------------------
    # Trading pair symbol mapping
    # ----------------------------------------------------------------

    def _initialize_trading_pair_symbols_from_exchange_info(
        self, exchange_info: Dict[str, Any]
    ):
        """
        Build trading pair symbol map.

        For Kuru, the trading pair is derived from MarketConfig.market_symbol
        (e.g., "MON-USDC") and maps 1:1 with the Hummingbot trading pair.
        """
        from bidict import bidict

        mapping = bidict()
        for pair in self._trading_pairs_list:
            mapping[pair] = pair  # exchange symbol == hummingbot symbol
        self._set_trading_pair_symbol_map(mapping)
