import asyncio
import binascii
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from random import randrange
from typing import Dict, Final, List, Optional, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from xrpl.asyncio.account import get_next_valid_seq_number
from xrpl.asyncio.clients import AsyncWebsocketClient, Client, XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.asyncio.transaction.main import _LEDGER_OFFSET, _calculate_fee_per_transaction_type, _tx_needs_networkID
from xrpl.models import Currency, IssuedCurrency, Request, Response, ServerInfo, Transaction, TransactionMetadata, Tx
from xrpl.models.requests.request import LookupByLedgerRequest, RequestMethod
from xrpl.models.utils import require_kwargs_on_init
from xrpl.utils.txn_parser.utils import NormalizedNode, normalize_nodes
from xrpl.utils.txn_parser.utils.order_book_parser import (
    _get_change_amount,
    _get_fields,
    _get_offer_status,
    _get_quality,
    _group_offer_changes_by_account,
)
from xrpl.utils.txn_parser.utils.types import AccountOfferChange, AccountOfferChanges, Balance, OfferChange
from yaml.representer import SafeRepresenter

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.client.config.config_validators import validate_with_regex
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.logger import HummingbotLogger

CENTRALIZED = True
EXAMPLE_PAIR = "XRP-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
    buy_percent_fee_deducted_from_returns=True,
)
_REQ_ID_MAX: Final[int] = 1_000_000


def get_order_book_changes(metadata: TransactionMetadata) -> List[AccountOfferChanges]:
    """
    Parse all order book changes from a transaction's metadata.

    Args:
        metadata: Transactions metadata.

    Returns:
        All offer changes caused by the transaction.
        The offer changes are grouped by their owner accounts.
    """
    return compute_order_book_changes(metadata)


def _get_offer_change(node: NormalizedNode) -> Optional[AccountOfferChange]:
    status = _get_offer_status(node)
    taker_gets = _get_change_amount(node, "TakerGets")
    taker_pays = _get_change_amount(node, "TakerPays")
    account = _get_fields(node, "Account")
    sequence = _get_fields(node, "Sequence")
    flags = _get_fields(node, "Flags")
    # if required fields are None: return None
    if (
        taker_gets is None
        or taker_pays is None
        or account is None
        or sequence is None
        # or flags is None # flags can be None
    ):
        return None

    expiration_time = _get_fields(node, "Expiration")
    quality = _get_quality(taker_gets, taker_pays)
    offer_change = OfferChange(
        flags=flags,
        taker_gets=taker_gets,
        taker_pays=taker_pays,
        sequence=sequence,
        status=status,
        maker_exchange_rate=quality,
    )
    if expiration_time is not None:
        offer_change["expiration_time"] = expiration_time
    return AccountOfferChange(maker_account=account, offer_change=offer_change)


def compute_order_book_changes(
    metadata: TransactionMetadata,
) -> List[AccountOfferChanges]:
    """
    Compute the offer changes from offer objects affected by the transaction.

    Args:
        metadata: Transactions metadata.

    Returns:
        All offer changes caused by the transaction.
        The offer changes are grouped by their owner accounts.
    """
    normalized_nodes = normalize_nodes(metadata)
    offer_nodes = [node for node in normalized_nodes if node["LedgerEntryType"] == "Offer"]
    offer_changes = []
    for node in offer_nodes:
        change = _get_offer_change(node)
        if change is not None:
            offer_changes.append(change)
    return _group_offer_changes_by_account(offer_changes)


def convert_string_to_hex(s, padding: bool = True):
    if len(s) > 3:
        hex_str = binascii.hexlify(s.encode()).decode()
        if padding:
            while len(hex_str) < 40:
                hex_str += "00"  # pad with zeros to reach 160 bits (40 hex characters)
        return hex_str.upper()

    return s


def get_token_from_changes(token_changes: List[Balance], token: str) -> Optional[Balance]:
    for token_change in token_changes:
        if token_change["currency"] == token:
            return token_change
    return None


class XRPLMarket(BaseModel):
    base: str
    quote: str
    base_issuer: str
    quote_issuer: str
    trading_pair_symbol: Optional[str] = None

    def __repr__(self):
        return str(self.model_dump())

    def get_token_symbol(self, code: str, issuer: str) -> Optional[str]:
        if self.trading_pair_symbol is None:
            return None

        if code.upper() == self.base.upper() and issuer.upper() == self.base_issuer.upper():
            return self.trading_pair_symbol.split("-")[0]

        if code.upper() == self.quote.upper() and issuer.upper() == self.quote_issuer.upper():
            return self.trading_pair_symbol.split("-")[1]

        return None


def represent_xrpl_market(dumper, data):
    return dumper.represent_dict(data.dict())


SafeRepresenter.add_representer(XRPLMarket, represent_xrpl_market)


@require_kwargs_on_init
@dataclass(frozen=True)
class Ledger(Request, LookupByLedgerRequest):
    """
    Retrieve information about the public ledger.
    `See ledger <https://xrpl.org/ledger.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.LEDGER, init=False)
    transactions: bool = False
    expand: bool = False
    owner_funds: bool = False
    binary: bool = False
    queue: bool = False


async def get_network_id_and_build_version(client: Client) -> None:
    """
    Get the network id and build version of the connected server.

    Args:
        client: The network client to use to send the request.

    Raises:
        XRPLRequestFailureException: if the rippled API call fails.
    """
    # the required values are already present, no need for further processing
    if client.network_id and client.build_version:
        return

    response = await client._request_impl(ServerInfo())
    if response.is_successful():
        if "network_id" in response.result["info"]:
            client.network_id = response.result["info"]["network_id"]
        if not client.build_version and "build_version" in response.result["info"]:
            client.build_version = response.result["info"]["build_version"]
        return

    raise XRPLRequestFailureException(response.result)


async def autofill(
    transaction: Transaction, client: Client, signers_count: Optional[int] = None, try_count: int = 0
) -> Transaction:
    """
    Autofills fields in a transaction. This will set `sequence`, `fee`, and
    `last_ledger_sequence` according to the current state of the server this Client is
    connected to. It also converts all X-Addresses to classic addresses.

    Args:
        transaction: the transaction to be signed.
        client: a network client.
        signers_count: the expected number of signers for this transaction.
            Only used for multisigned transactions.

    Returns:
        The autofilled transaction.
    """
    try:
        transaction_json = transaction.to_dict()
        if not client.network_id:
            await get_network_id_and_build_version(client)
        if "network_id" not in transaction_json and _tx_needs_networkID(client):
            transaction_json["network_id"] = client.network_id
        if "sequence" not in transaction_json:
            sequence = await get_next_valid_seq_number(transaction_json["account"], client)
            transaction_json["sequence"] = sequence
        if "fee" not in transaction_json:
            fee = int(await _calculate_fee_per_transaction_type(transaction, client, signers_count))
            fee = fee * CONSTANTS.FEE_MULTIPLIER
            transaction_json["fee"] = str(fee)
        if "last_ledger_sequence" not in transaction_json:
            ledger_sequence = await get_latest_validated_ledger_sequence(client)
            transaction_json["last_ledger_sequence"] = ledger_sequence + _LEDGER_OFFSET
        if "source_tag" not in transaction_json:
            transaction_json["source_tag"] = CONSTANTS.HBOT_SOURCE_TAG_ID
        return Transaction.from_dict(transaction_json)
    except Exception as e:
        if try_count < CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY:
            return await autofill(transaction, client, signers_count, try_count + 1)
        else:
            raise Exception(f"Autofill failed: {e}")


async def get_latest_validated_ledger_sequence(client: Client) -> int:
    """
    Returns the sequence number of the latest validated ledger.

    Args:
        client: The network client to use to send the request.

    Returns:
        The sequence number of the latest validated ledger.

    Raises:
        XRPLRequestFailureException: if the rippled API call fails.
    """

    request = Ledger(ledger_index="validated")
    request_dict = request.to_dict()
    request_dict["id"] = f"{request.method}_{randrange(_REQ_ID_MAX)}"
    request_with_id = Ledger.from_dict(request_dict)

    try:
        response = await client._request_impl(request_with_id)
    except KeyError as e:
        # KeyError can occur if the connection reconnects during the request,
        # which clears _open_requests in the XRPL library
        raise XRPLConnectionError(f"Request lost during reconnection: {e}")

    if response.is_successful():
        return cast(int, response.result["ledger_index"])

    raise XRPLRequestFailureException(response.result)


_LEDGER_CLOSE_TIME: Final[int] = 1


async def _sleep(seconds: int):
    await asyncio.sleep(seconds)


async def _wait_for_final_transaction_outcome(
    transaction_hash: str, client: Client, prelim_result: str, last_ledger_sequence: int
) -> Response:
    """
    The core logic of reliable submission.  Polls the ledger until the result of the
    transaction can be considered final, meaning it has either been included in a
    validated ledger, or the transaction's LastLedgerSequence has been surpassed by the
    latest ledger sequence (meaning it will never be included in a validated ledger).
    """
    await _sleep(_LEDGER_CLOSE_TIME)

    current_ledger_sequence = await get_latest_validated_ledger_sequence(client)

    if current_ledger_sequence >= last_ledger_sequence and (current_ledger_sequence - last_ledger_sequence) > 10:
        raise XRPLReliableSubmissionException(
            f"Transaction failed - latest ledger {current_ledger_sequence} exceeds "
            f"transaction's LastLedgerSequence {last_ledger_sequence}. Prelim result: {prelim_result}"
        )

    # query transaction by hash
    try:
        transaction_response = await client._request_impl(Tx(transaction=transaction_hash))
    except KeyError as e:
        # KeyError can occur if the connection reconnects during the request,
        # which clears _open_requests in the XRPL library
        raise XRPLConnectionError(f"Request lost during reconnection: {e}")

    if not transaction_response.is_successful():
        if transaction_response.result["error"] == "txnNotFound":
            """
            For the case if a submitted transaction is still
            in queue and not processed on the ledger yet.
            """
            return await _wait_for_final_transaction_outcome(
                transaction_hash, client, prelim_result, last_ledger_sequence
            )
        else:
            raise XRPLRequestFailureException(transaction_response.result)

    result = transaction_response.result
    if "validated" in result and result["validated"]:
        # result is in a validated ledger, outcome is final
        return_code = result["meta"]["TransactionResult"]
        if return_code != "tesSUCCESS":
            raise XRPLReliableSubmissionException(f"Transaction failed: {return_code}")
        return transaction_response

    # outcome is not yet final
    return await _wait_for_final_transaction_outcome(transaction_hash, client, prelim_result, last_ledger_sequence)


# AMM Interfaces
class PoolInfo(BaseModel):
    address: str
    base_token_address: Currency
    quote_token_address: Currency
    lp_token_address: IssuedCurrency
    fee_pct: Decimal
    price: Decimal
    base_token_amount: Decimal
    quote_token_amount: Decimal
    lp_token_amount: Decimal
    pool_type: Optional[str] = None


class GetPoolInfoRequest(BaseModel):
    network: Optional[str] = None
    pool_address: str


class AddLiquidityRequest(BaseModel):
    network: Optional[str] = None
    wallet_address: str
    pool_address: str
    base_token_amount: Decimal
    quote_token_amount: Decimal
    slippage_pct: Optional[Decimal] = None


class AddLiquidityResponse(BaseModel):
    signature: str
    fee: Decimal
    base_token_amount_added: Decimal
    quote_token_amount_added: Decimal


class QuoteLiquidityRequest(BaseModel):
    network: Optional[str] = None
    pool_address: str
    base_token_amount: Decimal
    quote_token_amount: Decimal
    slippage_pct: Optional[Decimal] = None


class QuoteLiquidityResponse(BaseModel):
    base_limited: bool
    base_token_amount: Decimal
    quote_token_amount: Decimal
    base_token_amount_max: Decimal
    quote_token_amount_max: Decimal


class RemoveLiquidityRequest(BaseModel):
    network: Optional[str] = None
    wallet_address: str
    pool_address: str
    percentage_to_remove: Decimal


class RemoveLiquidityResponse(BaseModel):
    signature: str
    fee: Decimal
    base_token_amount_removed: Decimal
    quote_token_amount_removed: Decimal


class XRPLConfigMap(BaseConnectorConfigMap):
    connector: str = "xrpl"
    xrpl_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your XRPL wallet secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    wss_node_urls: list[str] = Field(
        default=["wss://xrplcluster.com/", "wss://s1.ripple.com/", "wss://s2.ripple.com/"],
        json_schema_extra={
            "prompt": "Enter a list of XRPL Websocket Node URLs (comma separated)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    custom_markets: Dict[str, XRPLMarket] = Field(
        default={
            "SOLO-XRP": XRPLMarket(
                base="SOLO",
                quote="XRP",
                base_issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                quote_issuer="",
            )
        },
    )

    max_request_per_minute: int = Field(
        default=12,
        json_schema_extra={
            "prompt": "Maximum number of requests per minute to XRPL to avoid rate limits",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="xrpl")

    @field_validator("wss_node_urls", mode="before")
    @classmethod
    def validate_wss_node_urls(cls, v):
        if isinstance(v, str):
            v = [url.strip() for url in v.split(",") if url.strip()]
        pattern = r"^(wss://)[\w.-]+(:\d+)?(/[\w.-]*)*$"
        error_message = "Invalid node url. Node url should be in websocket format."
        for url in v:
            ret = validate_with_regex(url, pattern, error_message)
            if ret is not None:
                raise ValueError(f"{ret}: {url}")
        if not v:
            raise ValueError("At least one XRPL node URL must be provided.")
        return v


KEYS = XRPLConfigMap.model_construct()


# ============================================
# Custom Exception Classes (Phase 2)
# ============================================
class XRPLConnectionError(Exception):
    """Raised when all connections in the pool have failed."""
    pass


class XRPLTimeoutError(Exception):
    """Raised when a request times out."""
    pass


class XRPLTransactionError(Exception):
    """Raised when XRPL rejects a transaction."""
    pass


class XRPLSystemBusyError(Exception):
    """Raised when the request queue is full."""
    pass


class XRPLCircuitBreakerOpen(Exception):
    """Raised when too many failures have occurred."""
    pass


# ============================================
# XRPLConnection Dataclass (Phase 1)
# ============================================
@dataclass
class XRPLConnection:
    """
    Represents a persistent WebSocket connection to an XRPL node.
    Tracks connection health, latency metrics, and usage statistics.
    """
    url: str
    client: Optional[AsyncWebsocketClient] = None
    is_healthy: bool = True
    is_reconnecting: bool = False
    last_used: float = field(default_factory=time.time)
    last_health_check: float = field(default_factory=time.time)
    request_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    avg_latency: float = 0.0
    created_at: float = field(default_factory=time.time)

    def update_latency(self, latency: float, alpha: float = 0.3):
        """Update average latency using exponential moving average."""
        if self.avg_latency == 0.0:
            self.avg_latency = latency
        else:
            self.avg_latency = alpha * latency + (1 - alpha) * self.avg_latency

    def record_success(self):
        """Record a successful request."""
        self.request_count += 1
        self.consecutive_errors = 0
        self.last_used = time.time()

    def record_error(self):
        """Record a failed request."""
        self.error_count += 1
        self.consecutive_errors += 1
        self.last_used = time.time()

    @property
    def age(self) -> float:
        """Return the age of the connection in seconds."""
        return time.time() - self.created_at

    @property
    def is_open(self) -> bool:
        """Check if the underlying client connection is open."""
        return self.client is not None and self.client.is_open()


class RateLimiter:
    _logger = None

    def __init__(
        self, requests_per_10s: float, burst_tokens: int = 0, max_burst_tokens: int = 5, wait_margin_factor: float = 1.5
    ):
        """
        Simple rate limiter that measures and controls request rate in 10-second batches.

        Args:
            requests_per_10s: Maximum requests allowed per 10 seconds
            burst_tokens: Initial number of burst tokens available
            max_burst_tokens: Maximum number of burst tokens that can be accumulated
            wait_margin_factor: Multiplier for wait time to add safety margin (default 1.5)
        """
        self._rate_limit = requests_per_10s
        self._max_burst_tokens = max_burst_tokens
        self._burst_tokens = min(burst_tokens, max_burst_tokens)  # Ensure initial tokens don't exceed max
        self._request_times = deque(maxlen=1000)  # Store request timestamps for rate calculation
        self._last_rate_log = time.time()
        self._rate_log_interval = 10.0  # Log rate every 10 seconds
        self._wait_margin_factor = max(1.0, wait_margin_factor)  # Ensure factor is at least 1.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def _calculate_current_rate(self) -> float:
        """Calculate current request rate in requests per 10 seconds"""
        now = time.time()
        # Remove timestamps older than 10 seconds
        while self._request_times and now - self._request_times[0] > 10:
            self._request_times.popleft()

        if not self._request_times:
            return 0.0

        # Calculate rate over the last 10 seconds using a more accurate method
        request_count = len(self._request_times)

        # If we have less than 2 requests, rate is essentially 0
        if request_count < 2:
            return 0.0

        # Use the full 10-second window or the actual time span, whichever is larger
        # This prevents artificially high rates from short bursts
        time_span = now - self._request_times[0]
        measurement_window = max(10.0, time_span)

        # Calculate requests per 10 seconds based on the measurement window
        # This gives a more stable rate that doesn't spike for short bursts
        rate_per_second = request_count / measurement_window
        return rate_per_second * 10.0

    def _log_rate_status(self):
        """Log current rate status"""
        now = time.time()
        current_rate = self._calculate_current_rate()

        # Only log periodically to avoid spam
        if now - self._last_rate_log >= self._rate_log_interval:
            self.logger().debug(
                f"Rate status: {current_rate:.1f} req/10s (actual), "
                f"{self._rate_limit:.1f} req/10s (limit), "
                f"Burst tokens: {self._burst_tokens}/{self._max_burst_tokens}"
            )
            self._last_rate_log = now

    async def acquire(self, use_burst: bool = False) -> float:
        """
        Acquire permission to make a request. Returns wait time needed.

        Args:
            use_burst: Whether to use a burst token if available

        Returns:
            Wait time in seconds before proceeding (0 if no wait needed)
        """
        now = time.time()
        self._request_times.append(now)
        current_rate = self._calculate_current_rate()

        # If using burst token and tokens available, bypass rate limit
        if use_burst and self._burst_tokens > 0:
            self._burst_tokens -= 1
            self._log_rate_status()
            return 0.0

        # If under rate limit, proceed immediately
        if current_rate < self._rate_limit:
            self._log_rate_status()
            return 0.0

        # Calculate wait time needed to get under rate limit
        # We need to wait until enough old requests expire
        base_wait_time = 10.0 * (current_rate - self._rate_limit) / current_rate
        # Apply safety margin factor to wait longer and stay under limit
        wait_time = base_wait_time * self._wait_margin_factor
        self._log_rate_status()
        return wait_time

    def add_burst_tokens(self, tokens: int):
        """Add burst tokens that can be used to bypass rate limits"""
        if tokens <= 0:
            self.logger().warning(f"Attempted to add {tokens} burst tokens (must be positive)")
            return

        new_total = self._burst_tokens + tokens
        if new_total > self._max_burst_tokens:
            self._burst_tokens = self._max_burst_tokens
        else:
            self._burst_tokens = new_total
            self.logger().debug(f"Added {tokens} burst tokens. Total: {self._burst_tokens}")

    @property
    def burst_tokens(self) -> int:
        """Get current number of burst tokens available"""
        return self._burst_tokens


class XRPLNodePool:
    """
    Manages a pool of persistent WebSocket connections to XRPL nodes.

    Features:
    - Persistent connections (no connect/disconnect per request)
    - Health monitoring with automatic reconnection
    - Round-robin load balancing across healthy connections
    - Rate limiting to avoid node throttling
    - Graceful degradation when connections fail
    - Singleton pattern: shared across all XrplExchange instances
    """
    _logger = None
    DEFAULT_NODES = ["wss://xrplcluster.com/", "wss://s1.ripple.com/", "wss://s2.ripple.com/"]

    def __init__(
        self,
        node_urls: list[str],
        requests_per_10s: float = 18,  # About 2 requests per second
        burst_tokens: int = 0,
        max_burst_tokens: int = 5,
        health_check_interval: float = CONSTANTS.CONNECTION_POOL_HEALTH_CHECK_INTERVAL,
        connection_timeout: float = CONSTANTS.CONNECTION_POOL_TIMEOUT,
        max_connection_age: float = CONSTANTS.CONNECTION_POOL_MAX_AGE,
        wait_margin_factor: float = 1.5,
        cooldown: int = 600,
    ):
        """
        Initialize XRPLNodePool with persistent connections and rate limiting.

        Args:
            node_urls: List of XRPL node URLs
            requests_per_10s: Maximum requests allowed per 10 seconds
            burst_tokens: Initial number of burst tokens available
            max_burst_tokens: Maximum number of burst tokens that can be accumulated
            health_check_interval: Seconds between health checks
            connection_timeout: Connection timeout in seconds
            max_connection_age: Maximum age of a connection before refresh
            wait_margin_factor: Multiplier for wait time to add safety margin
            cooldown: (Legacy) Kept for backward compatibility
        """
        if not node_urls or len(node_urls) == 0:
            node_urls = self.DEFAULT_NODES.copy()

        self._node_urls = list(node_urls)
        self._init_time = time.time()

        # Connection pool state
        self._connections: Dict[str, XRPLConnection] = {}
        self._healthy_connections: deque = deque()
        self._connection_lock = asyncio.Lock()

        # Configuration
        self._health_check_interval = health_check_interval
        self._connection_timeout = connection_timeout
        self._max_connection_age = max_connection_age

        # State management
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._proactive_ping_task: Optional[asyncio.Task] = None

        # Initialize rate limiter
        self._rate_limiter = RateLimiter(
            requests_per_10s=requests_per_10s,
            burst_tokens=burst_tokens,
            max_burst_tokens=max_burst_tokens,
            wait_margin_factor=wait_margin_factor,
        )

        # Legacy compatibility
        self._cooldown = cooldown
        self._bad_nodes: Dict[str, float] = {}

        self.logger().debug(
            f"Initialized XRPLNodePool with {len(node_urls)} nodes, "
            f"rate limit: {requests_per_10s} req/10s, "
            f"burst tokens: {burst_tokens}/{max_burst_tokens}, "
            f"health check interval: {health_check_interval}s"
        )

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    def is_running(self) -> bool:
        """Check if the node pool is currently running."""
        return self._running

    async def start(self):
        """
        Initialize connections to all nodes and start health monitoring.
        Should be called before using the pool.
        """
        if self._running:
            self.logger().warning("XRPLNodePool is already running")
            return

        self._running = True
        self.logger().debug("Starting XRPLNodePool - initializing connections...")

        # Initialize connections in parallel
        init_tasks = [self._init_connection(url) for url in self._node_urls]
        results = await asyncio.gather(*init_tasks, return_exceptions=True)

        # Log initialization results
        successful = sum(1 for r in results if r is True)
        self.logger().debug(
            f"Connection initialization complete: {successful}/{len(self._node_urls)} connections established"
        )

        if successful == 0:
            self.logger().error("Failed to establish any connections - pool will operate in degraded mode")

        # Start health monitor
        self._health_check_task = asyncio.create_task(self._health_monitor_loop())
        self.logger().debug("Health monitor started")

        # Start proactive ping loop for early staleness detection
        self._proactive_ping_task = asyncio.create_task(self._proactive_ping_loop())
        self.logger().debug("Proactive ping loop started")

    async def stop(self):
        """
        Stop health monitoring and close all connections gracefully.
        """
        if not self._running:
            self.logger().warning("XRPLNodePool is not running")
            return

        self._running = False
        self.logger().debug("Stopping XRPLNodePool...")

        # Cancel health check task
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        # Cancel proactive ping task
        if self._proactive_ping_task is not None:
            self._proactive_ping_task.cancel()
            try:
                await self._proactive_ping_task
            except asyncio.CancelledError:
                pass
            self._proactive_ping_task = None

        # Close all connections
        async with self._connection_lock:
            close_tasks = []
            for url, conn in self._connections.items():
                if conn.client is not None and conn.is_open:
                    close_tasks.append(self._close_connection_safe(conn))

            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)

            self._connections.clear()
            self._healthy_connections.clear()

        self.logger().debug("XRPLNodePool stopped")

    async def _close_connection_safe(self, conn: XRPLConnection):
        """Safely close a connection without raising exceptions."""
        try:
            if conn.client is not None:
                await conn.client.close()
        except Exception as e:
            self.logger().debug(f"Error closing connection to {conn.url}: {e}")

    async def _init_connection(self, url: str) -> bool:
        """
        Initialize a persistent connection to a node.

        Args:
            url: The WebSocket URL to connect to

        Returns:
            True if connection was established successfully
        """
        try:
            client = AsyncWebsocketClient(url)

            # Open the connection
            await asyncio.wait_for(client.open(), timeout=self._connection_timeout)

            # Configure WebSocket settings
            if client._websocket is not None:
                client._websocket.max_size = CONSTANTS.WEBSOCKET_MAX_SIZE_BYTES
                client._websocket.ping_interval = 10
                client._websocket.ping_timeout = CONSTANTS.WEBSOCKET_CONNECTION_TIMEOUT

            # Test connection with ServerInfo request and measure latency
            start_time = time.time()
            response = await asyncio.wait_for(
                client._request_impl(ServerInfo()),
                timeout=self._connection_timeout
            )
            latency = time.time() - start_time

            if not response.is_successful():
                self.logger().warning(f"ServerInfo request failed for {url}: {response.result}")
                await client.close()
                return False

            # Create connection object
            conn = XRPLConnection(url=url, client=client)
            conn.update_latency(latency)

            async with self._connection_lock:
                self._connections[url] = conn
                self._healthy_connections.append(url)

            self.logger().debug(f"Connection established to {url} (latency: {latency:.3f}s)")
            return True

        except asyncio.TimeoutError:
            self.logger().warning(f"Connection timeout for {url}")
            return False
        except Exception as e:
            self.logger().warning(f"Failed to connect to {url}: {e}")
            return False

    async def get_client(self, use_burst: bool = True) -> AsyncWebsocketClient:
        """
        Get an already-connected WebSocket client from the pool.

        This method returns a persistent connection that is already open.
        The caller should NOT close the client - it will be reused.

        Args:
            use_burst: Whether to use a burst token if available

        Returns:
            An open AsyncWebsocketClient

        Raises:
            XRPLConnectionError: If no healthy connections are available
        """
        # Apply rate limiting (except during brief startup period)
        if time.time() - self._init_time > 10:
            wait_time = await self._rate_limiter.acquire(use_burst)
            if wait_time > 0:
                self.logger().debug(f"Rate limited: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        async with self._connection_lock:
            # Try to find a healthy, open connection
            attempts = 0
            max_attempts = len(self._healthy_connections) + 1

            while attempts < max_attempts and self._healthy_connections:
                attempts += 1

                # Round-robin: rotate and get the next connection
                url = self._healthy_connections[0]
                self._healthy_connections.rotate(-1)

                conn = self._connections.get(url)
                if conn is None:
                    continue

                # Check if connection is still open
                if not conn.is_open:
                    self.logger().debug(f"Connection to {url} is closed, triggering reconnection")
                    if not conn.is_reconnecting:
                        # Trigger background reconnection
                        asyncio.create_task(self._reconnect(url))
                    continue

                # Check if connection is healthy
                if not conn.is_healthy:
                    continue

                # Check if connection is currently reconnecting - skip to avoid race conditions
                # where _open_requests gets cleared during reconnection causing KeyError
                if conn.is_reconnecting:
                    self.logger().debug(f"Connection to {url} is reconnecting, skipping")
                    continue

                # Found a good connection
                conn.record_success()
                return conn.client  # type: ignore

            # No healthy connections available
            # Try to reconnect to any node
            self.logger().warning("No healthy connections available, attempting parallel emergency reconnection")

        # Emergency: try to establish connections to ALL nodes in parallel
        # This reduces the worst-case latency from N*timeout to 1*timeout
        # init_tasks = [self._init_connection(url) for url in self._node_urls]
        # results = await asyncio.gather(*init_tasks, return_exceptions=True)

        # # Return the first successfully connected client
        # for url, result in zip(self._node_urls, results):
        #     if result is True:
        #         conn = self._connections.get(url)
        #         if conn and conn.client and conn.is_open:
        #             self.logger().info(f"Emergency reconnection succeeded via {url}")
        #             return conn.client

        raise XRPLConnectionError("No healthy connections available and unable to establish new connections")

    async def _reconnect(self, url: str):
        """
        Reconnect to a specific node.

        Args:
            url: The URL to reconnect to
        """
        # Use lock to atomically check and set is_reconnecting flag
        async with self._connection_lock:
            conn = self._connections.get(url)
            if conn is None:
                return

            if conn.is_reconnecting:
                self.logger().debug(f"Already reconnecting to {url}")
                return

            conn.is_reconnecting = True

            # Remove from healthy list while holding lock
            if url in self._healthy_connections:
                self._healthy_connections.remove(url)

        # Perform reconnection outside lock to avoid blocking other operations
        try:
            self.logger().debug(f"Reconnecting to {url}...")

            # Close old connection if exists
            if conn.client is not None:
                try:
                    await conn.client.close()
                except Exception:
                    pass

            # Initialize new connection
            success = await self._init_connection(url)
            if success:
                self.logger().debug(f"Successfully reconnected to {url}")
            else:
                self.logger().warning(f"Failed to reconnect to {url}")

        finally:
            if url in self._connections:
                self._connections[url].is_reconnecting = False

    async def _health_monitor_loop(self):
        """Background task that periodically checks connection health."""
        self.logger().debug("Health monitor loop started")
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                if self._running:
                    await self._check_all_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger().error(f"Error in health monitor: {e}")

        self.logger().debug("Health monitor loop stopped")

    async def _proactive_ping_loop(self):
        """
        Background task that sends proactive pings to detect stale connections early.

        This runs more frequently than the health monitor to catch WebSocket
        connection staleness before it causes transaction timeouts. If a ping
        fails, the connection is marked for reconnection.

        Uses PROACTIVE_PING_INTERVAL (15s by default) and
        CONNECTION_MAX_CONSECUTIVE_ERRORS (3 by default) for threshold.
        """
        self.logger().debug(
            f"Proactive ping loop started (interval={CONSTANTS.PROACTIVE_PING_INTERVAL}s, "
            f"error_threshold={CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS})"
        )

        while self._running:
            try:
                await asyncio.sleep(CONSTANTS.PROACTIVE_PING_INTERVAL)
                if not self._running:
                    break

                # Ping all healthy connections in parallel
                ping_tasks = []
                urls_to_ping = []

                for url in list(self._healthy_connections):
                    conn = self._connections.get(url)
                    if conn is not None and conn.is_open and not conn.is_reconnecting:
                        ping_tasks.append(self._ping_connection(conn))
                        urls_to_ping.append(url)

                if ping_tasks:
                    results = await asyncio.gather(*ping_tasks, return_exceptions=True)

                    for url, result in zip(urls_to_ping, results):
                        if isinstance(result, Exception) or result is False:
                            conn = self._connections.get(url)
                            if conn is not None:
                                conn.record_error()
                                if conn.consecutive_errors >= CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS:
                                    self.logger().warning(
                                        f"Proactive ping: {url} failed {conn.consecutive_errors} times, "
                                        f"triggering reconnection"
                                    )
                                    conn.is_healthy = False
                                    if not conn.is_reconnecting:
                                        asyncio.create_task(self._reconnect(url))
                        else:
                            # Success - reset error count
                            conn = self._connections.get(url)
                            if conn is not None:
                                conn.consecutive_errors = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger().error(f"Error in proactive ping loop: {e}")

        self.logger().debug("Proactive ping loop stopped")

    async def _ping_connection(self, conn: XRPLConnection) -> bool:
        """
        Send a lightweight ping to a connection to check if it's still responsive.

        Args:
            conn: The connection to ping

        Returns:
            True if ping succeeded, False otherwise
        """
        try:
            if conn.client is None or not conn.is_open:
                return False

            # Use ServerInfo as a lightweight ping (small response)
            start_time = time.time()
            response = await asyncio.wait_for(
                conn.client._request_impl(ServerInfo()),
                timeout=10.0
            )
            latency = time.time() - start_time
            conn.update_latency(latency)

            if response.is_successful():
                return True
            else:
                self.logger().debug(f"Proactive ping to {conn.url} returned error: {response.result}")
                return False

        except asyncio.TimeoutError:
            self.logger().debug(f"Proactive ping to {conn.url} timed out")
            return False
        except Exception as e:
            self.logger().debug(f"Proactive ping to {conn.url} failed: {e}")
            return False

    async def _check_all_connections(self):
        """Check health of all connections and refresh as needed."""
        now = time.time()

        for url in list(self._connections.keys()):
            conn = self._connections.get(url)
            if conn is None or conn.is_reconnecting:
                continue

            should_reconnect = False
            reason = ""

            # Check if connection is closed
            if not conn.is_open:
                should_reconnect = True
                reason = "connection closed"

            # Check if connection is too old
            elif conn.age > self._max_connection_age:
                should_reconnect = True
                reason = f"connection age ({conn.age:.0f}s) exceeds max ({self._max_connection_age}s)"

            # Ping check with ServerInfo
            elif conn.is_open and conn.client is not None:
                try:
                    start_time = time.time()
                    response = await asyncio.wait_for(
                        conn.client._request_impl(ServerInfo()),
                        timeout=10.0
                    )
                    latency = time.time() - start_time
                    conn.update_latency(latency)
                    conn.last_health_check = now

                    if not response.is_successful():
                        conn.record_error()
                        if conn.consecutive_errors >= CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS:
                            should_reconnect = True
                            reason = f"too many errors ({conn.consecutive_errors})"
                    else:
                        conn.is_healthy = True
                        conn.consecutive_errors = 0

                except asyncio.TimeoutError:
                    conn.record_error()
                    should_reconnect = True
                    reason = "health check timeout"
                except Exception as e:
                    conn.record_error()
                    should_reconnect = True
                    reason = f"health check error: {e}"

            if should_reconnect:
                self.logger().debug(f"Triggering reconnection for {url}: {reason}")
                conn.is_healthy = False
                asyncio.create_task(self._reconnect(url))

    def mark_error(self, client: AsyncWebsocketClient):
        """
        Mark that an error occurred on a connection.
        After consecutive errors, the connection will be marked unhealthy and reconnected.

        Args:
            client: The client that experienced an error
        """
        for url, conn in self._connections.items():
            if conn.client is client:
                conn.record_error()
                self.logger().debug(
                    f"Error recorded for {url}: consecutive errors = {conn.consecutive_errors}"
                )

                if conn.consecutive_errors >= CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS:
                    conn.is_healthy = False
                    self.logger().warning(
                        f"Connection to {url} marked unhealthy after {conn.consecutive_errors} errors"
                    )
                    if not conn.is_reconnecting:
                        asyncio.create_task(self._reconnect(url))
                break

    def mark_bad_node(self, url: str):
        """Legacy method: Mark a node as bad for cooldown seconds"""
        until = float(time.time() + self._cooldown)
        self._bad_nodes[url] = until
        self.logger().debug(f"Node marked as bad: {url} (cooldown until {until})")

        # Also mark the connection as unhealthy
        conn = self._connections.get(url)
        if conn is not None:
            conn.is_healthy = False
            if not conn.is_reconnecting:
                asyncio.create_task(self._reconnect(url))

    @property
    def current_node(self) -> str:
        """Legacy property: Return the current node URL"""
        if self._healthy_connections:
            return self._healthy_connections[0]
        return self._node_urls[0] if self._node_urls else self.DEFAULT_NODES[0]

    @property
    def healthy_connection_count(self) -> int:
        """Return the number of healthy connections."""
        return len(self._healthy_connections)

    @property
    def total_connection_count(self) -> int:
        """Return the total number of connections (healthy and unhealthy)."""
        return len(self._connections)

    def add_burst_tokens(self, tokens: int):
        """Add burst tokens that can be used to bypass rate limits"""
        self._rate_limiter.add_burst_tokens(tokens)

    @property
    def burst_tokens(self) -> int:
        """Get current number of burst tokens available"""
        return self._rate_limiter.burst_tokens


def parse_offer_create_transaction(tx: dict) -> dict:
    """
    Helper to parse an OfferCreate transaction and its metadata to extract price (quality) and quantity transferred.
    Args:
        tx: The transaction object (dict) as returned by XRPL.
    Returns:
        dict with keys: 'quality', 'taker_gets_transferred', 'taker_pays_transferred'
    """
    meta = tx.get("meta")
    if not meta or "AffectedNodes" not in meta:
        return {"quality": None, "taker_gets_transferred": None, "taker_pays_transferred": None}

    # Find the Offer node for the account and sequence in the transaction
    account = tx.get("Account")
    sequence = tx.get("Sequence")
    offer_node = None
    for node in meta["AffectedNodes"]:
        node_type = next(iter(node))
        node_data = node[node_type]
        if node_data.get("LedgerEntryType") == "Offer":
            fields = node_data.get("FinalFields", node_data.get("NewFields", {}))
            if fields.get("Account") == account and fields.get("Sequence") == sequence:
                offer_node = node_data
                break
    # If not found, just use the first Offer node
    if offer_node is None:
        for node in meta["AffectedNodes"]:
            node_type = next(iter(node))
            node_data = node[node_type]
            if node_data.get("LedgerEntryType") == "Offer":
                offer_node = node_data
                break
    # Compute transferred amounts from PreviousFields if available
    taker_gets_transferred = None
    taker_pays_transferred = None
    quality = None
    if offer_node:
        prev = offer_node.get("PreviousFields", {})
        final = offer_node.get("FinalFields", offer_node.get("NewFields", {}))
        gets_prev = prev.get("TakerGets")
        gets_final = final.get("TakerGets")
        pays_prev = prev.get("TakerPays")
        pays_final = final.get("TakerPays")
        # Only compute if both prev and final exist
        if gets_prev is not None and gets_final is not None:
            try:
                if isinstance(gets_prev, dict):
                    gets_prev_val = float(gets_prev["value"])
                    gets_final_val = float(gets_final["value"])
                else:
                    gets_prev_val = float(gets_prev)
                    gets_final_val = float(gets_final)
                taker_gets_transferred = gets_prev_val - gets_final_val
            except Exception:
                taker_gets_transferred = None
        if pays_prev is not None and pays_final is not None:
            try:
                if isinstance(pays_prev, dict):
                    pays_prev_val = float(pays_prev["value"])
                    pays_final_val = float(pays_final["value"])
                else:
                    pays_prev_val = float(pays_prev)
                    pays_final_val = float(pays_final)
                taker_pays_transferred = pays_prev_val - pays_final_val
            except Exception:
                taker_pays_transferred = None
        # Compute quality (price)
        if taker_gets_transferred and taker_pays_transferred and taker_gets_transferred != 0:
            try:
                quality = taker_pays_transferred / taker_gets_transferred
            except Exception:
                quality = None
    return {
        "quality": quality,
        "taker_gets_transferred": taker_gets_transferred,
        "taker_pays_transferred": taker_pays_transferred,
    }
