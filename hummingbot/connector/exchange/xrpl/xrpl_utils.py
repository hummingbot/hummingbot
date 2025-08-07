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

    response = await client._request_impl(request_with_id)
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
    transaction_response = await client._request_impl(Tx(transaction=transaction_hash))
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
    _logger = None
    DEFAULT_NODES = ["wss://xrplcluster.com/", "wss://s1.ripple.com/", "wss://s2.ripple.com/"]

    def __init__(
        self,
        node_urls: list[str],
        requests_per_10s: float = 18,  # About 2 requests per second
        burst_tokens: int = 0,
        max_burst_tokens: int = 5,
        proactive_switch_interval: int = 30,
        cooldown: int = 600,
        wait_margin_factor: float = 1.5,
    ):
        """
        Initialize XRPLNodePool with rate limiting.

        Args:
            node_urls: List of XRPL node URLs
            requests_per_10s: Maximum requests allowed per 10 seconds
            burst_tokens: Initial number of burst tokens available
            max_burst_tokens: Maximum number of burst tokens that can be accumulated
            proactive_switch_interval: Seconds between proactive node switches (0 to disable)
            cooldown: Seconds a node is considered bad after being rate-limited
            wait_margin_factor: Multiplier for wait time to add safety margin (default 1.5)
        """
        if not node_urls or len(node_urls) == 0:
            node_urls = self.DEFAULT_NODES.copy()
        self._nodes = deque(node_urls)
        self._bad_nodes = {}  # url -> timestamp when it becomes good again
        self._lock = asyncio.Lock()
        self._last_switch_time = time.time()
        self._proactive_switch_interval = proactive_switch_interval
        self._cooldown = cooldown
        self._current_node = self._nodes[0]
        self._last_used_node = self._current_node
        self._init_time = time.time()

        # Initialize rate limiter
        self._rate_limiter = RateLimiter(
            requests_per_10s=requests_per_10s,
            burst_tokens=burst_tokens,
            max_burst_tokens=max_burst_tokens,
            wait_margin_factor=wait_margin_factor,
        )
        self.logger().info(
            f"Initialized XRPLNodePool with {len(node_urls)} nodes, "
            f"rate limit: {requests_per_10s} req/10s, "
            f"burst tokens: {burst_tokens}/{max_burst_tokens}"
        )

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    async def get_node(self, use_burst: bool = True) -> str:
        """
        Get a node URL to use, respecting rate limits and node health.
        This will wait if necessary to respect rate limits.

        Args:
            use_burst: Whether to use a burst token if available

        Returns:
            A node URL to use
        """
        async with self._lock:
            now = time.time()

            # Remove nodes from bad list if cooldown expired
            self._bad_nodes = {
                url: until for url, until in self._bad_nodes.items() if isinstance(until, (int, float)) and until > now
            }

            # Proactive switch if interval passed or current node is bad
            if (
                self._proactive_switch_interval > 0 and now - self._last_switch_time > self._proactive_switch_interval
            ) or self._current_node in self._bad_nodes:
                self.logger().debug(f"Switching node: proactive or current node is bad. Current: {self._current_node}")
                await self._rotate_node_locked(now)

            if time.time() - self._init_time > 40:
                wait_time = await self._rate_limiter.acquire(use_burst)
                self.logger().debug(f"Rate limited: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            return self._current_node

    def mark_bad_node(self, url: str):
        """Mark a node as bad for cooldown seconds"""
        until = float(time.time() + self._cooldown)
        self._bad_nodes[url] = until
        self.logger().info(f"Node marked as bad: {url} (cooldown until {until})")
        if url == self._current_node:
            self.logger().debug(f"Current node {url} is bad, rotating node.")
            asyncio.create_task(self._rotate_node_locked(time.time()))

    async def get_latency(self, node: str) -> float:
        """Get the latency of a node"""
        try:
            client = AsyncWebsocketClient(node)
            start_time = time.time()
            await client.open()
            await client._request_impl(ServerInfo())
            latency = time.time() - start_time
            await client.close()
            return latency
        except Exception as e:
            self.logger().error(f"Error getting latency for node {node}: {e}")
            return 9999

    async def _get_latency_safe(self, node: str) -> float:
        """Get latency of a node without marking it as bad if it fails"""
        try:
            client = AsyncWebsocketClient(node)
            start_time = time.time()
            await client.open()
            await client._request_impl(ServerInfo())
            latency = time.time() - start_time
            await client.close()
            return latency
        except Exception as e:
            self.logger().debug(f"Error getting latency for node {node} during rotation: {e}")
            return 9999

    async def _rotate_node_locked(self, now: float):
        """Rotate to the next good node"""
        checked_nodes = set()
        while len(checked_nodes) < len(self._nodes):
            self._nodes.rotate(-1)
            candidate = self._nodes[0]

            # Skip if we've already checked this node
            if candidate in checked_nodes:
                continue
            checked_nodes.add(candidate)

            # Skip if node is in bad list and cooldown hasn't expired
            if candidate in self._bad_nodes:
                cooldown_until = self._bad_nodes[candidate]
                if isinstance(cooldown_until, (int, float)) and cooldown_until > now:
                    self.logger().debug(f"Skipping node {candidate} - still in cooldown until {cooldown_until}")
                    continue
                else:
                    # Cooldown expired, remove from bad nodes
                    self._bad_nodes.pop(candidate, None)
                    self.logger().debug(f"Node {candidate} cooldown expired, removing from bad nodes")

            # Check latency
            latency = await self._get_latency_safe(candidate)
            if latency >= 9999 or latency > 5.0:  # 5 seconds max acceptable latency
                self.logger().warning(f"Node {candidate} has high latency ({latency:.2f}s), marking as bad")
                self.mark_bad_node(candidate)
                continue

            # Found a good node
            self.logger().info(f"Rotated to new XRPL node: {candidate} (latency: {latency:.2f}s)")
            self._current_node = candidate
            self._last_switch_time = now
            return

        # If we get here, all nodes are bad
        self.logger().warning("All nodes have high latency or are marked as bad, using first node as fallback")
        self._current_node = self._nodes[0]
        self._last_switch_time = now

    @property
    def current_node(self) -> str:
        return self._current_node

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
