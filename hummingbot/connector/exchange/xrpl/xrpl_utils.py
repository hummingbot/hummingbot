import asyncio
import binascii
from dataclasses import dataclass, field
from decimal import Decimal
from random import randrange
from typing import Any, Dict, Final, List, Optional, cast

from pydantic import BaseModel, Field, SecretStr, validator
from xrpl.asyncio.account import get_next_valid_seq_number
from xrpl.asyncio.clients import Client, XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.asyncio.transaction.main import (
    _LEDGER_OFFSET,
    _calculate_fee_per_transaction_type,
    _get_network_id_and_build_version,
    _tx_needs_networkID,
)
from xrpl.models import Request, Response, Transaction, TransactionMetadata, Tx
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
from xrpl.utils.txn_parser.utils.types import AccountOfferChange, AccountOfferChanges, OfferChange
from yaml.representer import SafeRepresenter

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.client.config.config_validators import validate_with_regex
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

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


def get_token_from_changes(token_changes: [Dict[str, Any]], token: str) -> Optional[Dict[str, Any]]:
    for token_change in token_changes:
        if token_change.get("currency") == token:
            return token_change
    return None


class XRPLMarket(BaseModel):
    base: str
    quote: str
    base_issuer: str
    quote_issuer: str
    trading_pair_symbol: Optional[str] = None

    def __repr__(self):
        return str(self.dict())

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
            await _get_network_id_and_build_version(client)
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


async def _wait_for_final_transaction_outcome(
    transaction_hash: str, client: Client, prelim_result: str, last_ledger_sequence: int
) -> Response:
    """
    The core logic of reliable submission.  Polls the ledger until the result of the
    transaction can be considered final, meaning it has either been included in a
    validated ledger, or the transaction's LastLedgerSequence has been surpassed by the
    latest ledger sequence (meaning it will never be included in a validated ledger).
    """
    await asyncio.sleep(_LEDGER_CLOSE_TIME)

    current_ledger_sequence = await get_latest_validated_ledger_sequence(client)

    if current_ledger_sequence >= last_ledger_sequence:
        raise XRPLReliableSubmissionException(
            f"The latest validated ledger sequence {current_ledger_sequence} is "
            f"greater than LastLedgerSequence {last_ledger_sequence} in "
            f"the transaction. Prelim result: {prelim_result}"
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


class XRPLConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="xrpl", const=True, client_data=None)
    xrpl_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your XRPL wallet secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    wss_node_url = Field(
        default="wss://xrplcluster.com/",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your XRPL Websocket Node URL",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    wss_second_node_url = Field(
        default="wss://s1.ripple.com/",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your second XRPL Websocket Node URL",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    wss_third_node_url = Field(
        default="wss://s2.ripple.com/",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your third XRPL Websocket Node URL",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
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
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter custom markets: ", is_connect_key=True, prompt_on_new=False
        ),
    )

    class Config:
        title = "xrpl"

    @validator("xrpl_secret_key", pre=True)
    def validate_xrpl_secret_key(cls, v: str):
        pattern = r"^s[A-HJ-NP-Za-km-z1-9]*$"
        error_message = "Invalid XRPL wallet secret key. Secret key should be a base 58 string and start with 's'."
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("wss_node_url", pre=True)
    def validate_wss_node_url(cls, v: str):
        pattern = r"^(wss://)[\w.-]+(:\d+)?(/[\w.-]*)*$"
        error_message = "Invalid node url. Node url should be in websocket format."
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("wss_second_node_url", pre=True)
    def validate_wss_second_node_url(cls, v: str):
        pattern = r"^(wss://)[\w.-]+(:\d+)?(/[\w.-]*)*$"
        error_message = "Invalid node url. Node url should be in websocket format."
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("wss_third_node_url", pre=True)
    def validate_wss_third_node_url(cls, v: str):
        pattern = r"^(wss://)[\w.-]+(:\d+)?(/[\w.-]*)*$"
        error_message = "Invalid node url. Node url should be in websocket format."
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v


KEYS = XRPLConfigMap.construct()
