import binascii
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, SecretStr, validator
from xrpl.models import TransactionMetadata
from xrpl.utils.txn_parser.utils import NormalizedNode, normalize_nodes
from xrpl.utils.txn_parser.utils.order_book_parser import (
    _get_change_amount,
    _get_fields,
    _get_offer_status,
    _get_quality,
    _group_offer_changes_by_account,
)
from xrpl.utils.txn_parser.utils.types import AccountOfferChange, AccountOfferChanges, OfferChange

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
    offer_nodes = [
        node for node in normalized_nodes if node["LedgerEntryType"] == "Offer"
    ]
    offer_changes = []
    for node in offer_nodes:
        change = _get_offer_change(node)
        if change is not None:
            offer_changes.append(change)
    return _group_offer_changes_by_account(offer_changes)


def normalize_price_from_drop(price: str, is_ask: bool = False) -> float:
    drop = CONSTANTS.ONE_DROP

    if is_ask:
        return round(float(Decimal(price) * drop), 6)

    return round(float(Decimal(price) / drop), 6)


def convert_string_to_hex(s):
    if len(s) > 3:
        hex_str = binascii.hexlify(s.encode()).decode()
        while len(hex_str) < 40:
            hex_str += '00'  # pad with zeros to reach 160 bits (40 hex characters)
        return hex_str.upper()

    return s


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
        default="wss://s1.ripple.com/",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your XRPL Websocket Node URL",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "xrpl"

    @validator("xrpl_secret_key", pre=True)
    def validate_xrpl_secret_key(cls, v: str):
        pattern = r'^s[1-9A-HJ-NP-Za-km-z]{1,28}$'
        error_message = "Invalid XRPL wallet secret key. Secret key should be a base 58 string and start with 's'."
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v

    @validator("wss_node_url", pre=True)
    def validate_wss_node_url(cls, v: str):
        pattern = r'^(wss://)[\w.-]+(:\d+)?(/[\w.-]*)*$'
        error_message = "Invalid node url. Node url should be in websocket format."
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v


KEYS = XRPLConfigMap.construct()
