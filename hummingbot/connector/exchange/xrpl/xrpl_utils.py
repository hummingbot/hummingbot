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
from xrpl.asyncio.clients import Client, XRPLRequestFailureException
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

    lock_delay_seconds: int = Field(
        default=10,
        json_schema_extra={
            "prompt": "Delay (in seconds) for requests to XRPL to avoid rate limits",
            "is_secure": False,
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


class XRPLNodePool:
    _logger = None
    DEFAULT_NODES = ["wss://xrplcluster.com/", "wss://s1.ripple.com/", "wss://s2.ripple.com/"]

    def __init__(self, node_urls: list[str], proactive_switch_interval: int = 30, cooldown: int = 600, delay: int = 5):
        """
        :param node_urls: List of XRPL node URLs
        :param proactive_switch_interval: Seconds between proactive node switches (0 to disable)
        :param cooldown: Seconds a node is considered bad after being rate-limited (default 600s = 10min)
        :param delay: Initial delay in seconds for rate limiting (default 5s)
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
        self._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(self.__class__))
        self._max_delay = delay
        self._base_delay = 1.0  # Base delay in seconds
        self._delay = 0.0
        self._retry_count = 0
        self._init_time = time.time()
        self._gentle_retry_limit = 3  # Number of retries before switching to steeper increase

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    async def get_node(self) -> str:
        async with self._lock:
            now = time.time()
            # Remove nodes from bad list if cooldown expired, and skip non-numeric until values
            self._bad_nodes = {
                url: until for url, until in self._bad_nodes.items() if isinstance(until, (int, float)) and until > now
            }
            # Proactive switch if interval passed or current node is bad
            if (
                self._proactive_switch_interval > 0 and now - self._last_switch_time > self._proactive_switch_interval
            ) or self._current_node in self._bad_nodes:
                self.logger().info(f"Switching node: proactive or current node is bad. Current: {self._current_node}")
                self._rotate_node_locked(now)
                # Reset retry count when switching nodes
                self._retry_count = 0
                self._delay = 0.0

            # Add artificial wait with exponential backoff
            await asyncio.sleep(self._delay)
            self.logger().info(f"Selected XRPL node: {self._current_node}")

            # Increase delay exponentially only after 30 seconds from init
            if time.time() - self._init_time > 30:
                # Use gentler increase (base 1.2) for first 5 retries, then steeper (base 2) after that
                if self._retry_count < self._gentle_retry_limit:
                    self._delay = min(self._base_delay * (1.2**self._retry_count), self._max_delay)
                else:
                    # For retries after gentle_retry_limit, use steeper increase
                    # Subtract gentle_retry_limit to start from a reasonable delay
                    adjusted_retry = self._retry_count - self._gentle_retry_limit
                    self._delay = min(self._base_delay * (2**adjusted_retry), self._max_delay)
                self._retry_count += 1

            return self._current_node

    def mark_bad_node(self, url: str):
        # Mark a node as bad for cooldown seconds
        until = float(time.time() + self._cooldown)
        self._bad_nodes[url] = until
        self.logger().info(f"Node marked as bad: {url} (cooldown until {until})")
        # If the current node is bad, rotate immediately
        if url == self._current_node:
            self.logger().info(f"Current node {url} is bad, rotating node.")
            self._rotate_node_locked(time.time())

    def _rotate_node_locked(self, now: float):
        # Rotate to the next good node
        for _ in range(len(self._nodes)):
            self._nodes.rotate(-1)
            candidate = self._nodes[0]
            if candidate not in self._bad_nodes:
                self.logger().info(f"Rotated to new XRPL node: {candidate}")
                self._current_node = candidate
                self._last_switch_time = now
                return
        # If all nodes are bad, just use the next one (will likely fail)
        self.logger().info(f"All nodes are bad, using: {self._nodes[0]}")
        self._current_node = self._nodes[0]
        self._last_switch_time = now

    def set_delay(self, delay: float):
        """Set a custom delay and reset retry count"""
        self._delay = min(delay, self._max_delay)
        self._retry_count = 0

    @property
    def current_node(self) -> str:
        return self._current_node
