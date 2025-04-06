"""High-level transaction methods with XRPL transactions."""

import math
from typing import Any, Dict, Optional, cast

from typing_extensions import Final

from xrpl.asyncio.account import get_next_valid_seq_number
from xrpl.asyncio.clients import Client, XRPLRequestFailureException
from xrpl.asyncio.ledger import get_fee, get_latest_validated_ledger_sequence
from xrpl.constants import XRPLException
from xrpl.core.addresscodec import is_valid_xaddress, xaddress_to_classic_address
from xrpl.core.binarycodec import encode, encode_for_multisigning, encode_for_signing
from xrpl.core.keypairs.main import sign as keypairs_sign
from xrpl.models.requests import ServerInfo, ServerState, SubmitOnly
from xrpl.models.response import Response
from xrpl.models.transactions import EscrowFinish
from xrpl.models.transactions.transaction import Signer, Transaction
from xrpl.models.transactions.transaction import (
    transaction_json_to_binary_codec_form as model_transaction_to_binary_codec,
)
from xrpl.models.transactions.types.transaction_type import TransactionType
from xrpl.utils import drops_to_xrp, xrp_to_drops
from xrpl.wallet.main import Wallet

_LEDGER_OFFSET: Final[int] = 20
# Sidechains are expected to have network IDs above this.
# Networks with ID above this restricted number are expected to specify an
# accurate NetworkID field in every transaction to that chain to prevent replay attacks.
# Mainnet and testnet are exceptions.
# More context: https://github.com/XRPLF/rippled/pull/4370
_RESTRICTED_NETWORKS = 1024
_REQUIRED_NETWORKID_VERSION = "1.11.0"


async def sign_and_submit(
    transaction: Transaction,
    client: Client,
    wallet: Wallet,
    autofill: bool = True,
    check_fee: bool = True,
) -> Response:
    """
    Signs a transaction (locally, without trusting external rippled nodes) and submits
    it to the XRPL.

    Args:
        transaction: the transaction to be signed and submitted.
        client: the network client with which to submit the transaction.
        wallet: the wallet with which to sign the transaction.
        autofill: whether to autofill the relevant fields. Defaults to True.
        check_fee: whether to check if the fee is higher than the expected transaction
            type fee. Defaults to True.

    Returns:
        The response from the ledger.
    """
    if autofill:
        transaction = await autofill_and_sign(transaction, client, wallet, check_fee)
    else:
        if check_fee:
            await _check_fee(transaction, client)
        transaction = sign(transaction, wallet)
    return await submit(transaction, client)


# Even though this is synchronous - this is here because it used to be async in
# xrpl-py 1.0, and we decided it wasn't worth breaking people's imports to move
# It to a central location as part of the xrpl-py 2.0 changes. It is aliased in
# The synchronous half of the library as well.
def sign(
    transaction: Transaction,
    wallet: Wallet,
    multisign: bool = False,
) -> Transaction:
    """
    Signs a transaction locally, without trusting external rippled nodes.

    Args:
        transaction: the transaction to be signed.
        wallet: the wallet with which to sign the transaction.
        multisign: whether to sign the transaction for a multisignature transaction.

    Returns:
        The signed transaction blob.
    """
    if multisign:
        signature = keypairs_sign(
            bytes.fromhex(
                encode_for_multisigning(
                    transaction.to_xrpl(),
                    wallet.address,
                )
            ),
            wallet.private_key,
        )
        tx_dict = transaction.to_dict()
        tx_dict["signers"] = [
            Signer(
                account=wallet.address,
                txn_signature=signature,
                signing_pub_key=wallet.public_key,
            )
        ]
        return Transaction.from_dict(tx_dict)

    transaction_json = _prepare_transaction(transaction, wallet)
    serialized_for_signing = encode_for_signing(transaction_json)
    serialized_bytes = bytes.fromhex(serialized_for_signing)
    signature = keypairs_sign(serialized_bytes, wallet.private_key)
    transaction_json["TxnSignature"] = signature
    return Transaction.from_xrpl(transaction_json)


async def autofill_and_sign(
    transaction: Transaction,
    client: Client,
    wallet: Wallet,
    check_fee: bool = True,
) -> Transaction:
    """
    Autofills relevant fields. Then, signs a transaction locally, without trusting
    external rippled nodes.

    Args:
        transaction: the transaction to be signed.
        wallet: the wallet with which to sign the transaction.
        client: a network client.
        check_fee: whether to check if the fee is higher than the expected transaction
            type fee. Defaults to True.

    Returns:
        The signed transaction.
    """
    # We do the transaction fee check here as we have the Client available.
    # The fee check will be done if transaction.fee exists. Otherwise the fee
    # will be auto-filled in autofill()
    if check_fee:
        await _check_fee(transaction, client)

    return sign(await autofill(transaction, client), wallet, multisign=False)


async def submit(
    transaction: Transaction,
    client: Client,
    *,
    fail_hard: bool = False,
) -> Response:
    """
    Submits a transaction to the ledger.

    Args:
        transaction: the Transaction to be submitted.
        client: the network client with which to submit the transaction.
        fail_hard: an optional boolean. If True, and the transaction fails for
            the initial server, do not retry or relay the transaction to other
            servers. Defaults to False.

    Returns:
        The response from the ledger.

    Raises:
        XRPLRequestFailureException: if the rippled API call fails.
    """
    transaction_blob = encode(transaction.to_xrpl())
    response = await client._request_impl(
        SubmitOnly(tx_blob=transaction_blob, fail_hard=fail_hard)
    )
    if response.is_successful():
        return response

    raise XRPLRequestFailureException(response.result)


def _prepare_transaction(
    transaction: Transaction,
    wallet: Wallet,
) -> Dict[str, Any]:
    """
    Prepares a Transaction by converting it to a JSON-like dictionary, converting the
    field names to CamelCase. If a Client is provided, then it also autofills any
    relevant fields.

    Args:
        transaction: the Transaction to be prepared.
        wallet: the wallet that will be used for signing.

    Returns:
        A JSON-like dictionary that is ready to be signed.

    Raises:
        XRPLException: if both LastLedgerSequence and `ledger_offset` are provided, or
            if an address tag is provided that does not match the X-Address tag.
    """
    transaction_json = transaction.to_xrpl()
    transaction_json["SigningPubKey"] = wallet.public_key

    _validate_account_xaddress(transaction_json, "Account", "SourceTag")
    if "Destination" in transaction_json:
        _validate_account_xaddress(transaction_json, "Destination", "DestinationTag")

    # DepositPreauth
    _convert_to_classic_address(transaction_json, "Authorize")
    _convert_to_classic_address(transaction_json, "Unauthorize")
    # EscrowCancel, EscrowFinish
    _convert_to_classic_address(transaction_json, "Owner")
    # SetRegularKey
    _convert_to_classic_address(transaction_json, "RegularKey")

    return transaction_json


async def autofill(
    transaction: Transaction, client: Client, signers_count: Optional[int] = None
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
    transaction_json = transaction.to_dict()
    if not client.network_id:
        await _get_network_id_and_build_version(client)
    if "network_id" not in transaction_json and _tx_needs_networkID(client):
        transaction_json["network_id"] = client.network_id
    if "sequence" not in transaction_json:
        sequence = await get_next_valid_seq_number(transaction_json["account"], client)
        transaction_json["sequence"] = sequence
    if "fee" not in transaction_json:
        transaction_json["fee"] = await _calculate_fee_per_transaction_type(
            transaction, client, signers_count
        )
    if "last_ledger_sequence" not in transaction_json:
        ledger_sequence = await get_latest_validated_ledger_sequence(client)
        transaction_json["last_ledger_sequence"] = ledger_sequence + _LEDGER_OFFSET
    return Transaction.from_dict(transaction_json)


async def _get_network_id_and_build_version(client: Client) -> None:
    """
    Get the network id and build version of the connected server.

    Args:
        client: The network client to use to send the request.

    Raises:
        XRPLRequestFailureException: if the rippled API call fails.
    """
    response = await client._request_impl(ServerInfo())
    if response.is_successful():
        if "network_id" in response.result["info"]:
            client.network_id = response.result["info"]["network_id"]
        if not client.build_version and "build_version" in response.result["info"]:
            client.build_version = response.result["info"]["build_version"]
        return

    raise XRPLRequestFailureException(response.result)


def _tx_needs_networkID(client: Client) -> bool:
    """
    Determines whether the transactions required network ID to be valid.
    Transaction needs networkID if later than restricted ID and either
        the network is hooks testnet or build version is >= 1.11.0.
    More context: https://github.com/XRPLF/rippled/pull/4370

    Args:
        client (Client): The network client to use to send the request.

    Returns:
        bool: whether the transactions required network ID to be valid
    """
    if client.network_id and client.network_id > _RESTRICTED_NETWORKS:
        if client.build_version and _is_not_later_rippled_version(
            _REQUIRED_NETWORKID_VERSION, client.build_version
        ):
            return True
    return False


def _is_not_later_rippled_version(source: str, target: str) -> bool:
    """
    Determines whether the source version is not a later release than the
        target version.

    Args:
        source: the source rippled version.
        target: the target rippled version.

    Returns:
        bool: true if source is earlier, false otherwise.
    """
    if source == target:
        return True
    source_decomp = source.split(".")
    target_decomp = target.split(".")
    source_major, source_minor = int(source_decomp[0]), int(source_decomp[1])
    target_major, target_minor = int(target_decomp[0]), int(target_decomp[1])

    # Compare major version
    if source_major != target_major:
        return source_major < target_major

    # Compare minor version
    if source_minor != target_minor:
        return source_minor < target_minor

    source_patch = source_decomp[2].split("-")
    target_patch = target_decomp[2].split("-")
    source_patch_version = int(source_patch[0])
    target_patch_version = int(target_patch[0])

    # Compare patch version
    if source_patch_version != target_patch_version:
        return source_patch_version < target_patch_version

    # Compare release version
    if len(source_patch) != len(target_patch):
        return len(source_patch) > len(target_patch)

    if len(source_patch) == 2:
        # Compare release types
        if not source_patch[1][0].startswith(target_patch[1][0]):
            return source_patch[1] < target_patch[1]
        # Compare beta versions
        if source_patch[1].startswith("b"):
            return int(source_patch[1][1:]) < int(target_patch[1][1:])
        # Compare rc versions
        return int(source_patch[1][2:]) < int(target_patch[1][2:])
    return False


def _validate_account_xaddress(
    json: Dict[str, Any], account_field: str, tag_field: str
) -> None:
    """
    Mutates JSON-like dictionary so the X-Address in the account field is the classic
    address, and the tag is in the tag field.

    Args:
        json: JSON-like dictionary with transaction data or similar
        account_field: the field of `json` that may contain an X-Address
        tag_field: the field of `json` that may contain a source or destination tag

    Raises:
        XRPLException: if both an X-Address containing a tag and a tag field are
            provided and they do not match.
    """
    if is_valid_xaddress(json[account_field]):
        account, tag, _ = xaddress_to_classic_address(json[account_field])
        json[account_field] = account
        if tag_field in json and json[tag_field] != tag:
            raise XRPLException(f"{tag_field} value does not match X-Address tag")
        json[tag_field] = tag


def _convert_to_classic_address(json: Dict[str, Any], field: str) -> None:
    """
    Mutates JSON-like dictionary to convert the given field from an X-Address (if
    applicable) to a classic address.

    Args:
        json: JSON-like dictionary with transaction data or similar
        field: the field in `json` that may contain an X-Address
    """
    if field in json and is_valid_xaddress(json[field]):
        json[field] = xaddress_to_classic_address(json[field])


def transaction_json_to_binary_codec_form(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a new dictionary in which the keys have been formatted as CamelCase and
    standardized to be serialized by the binary codec.

    Args:
        dictionary: The dictionary to be reformatted.

    Returns:
        A new dictionary object that has been reformatted.
    """
    return model_transaction_to_binary_codec(dictionary)


async def _check_fee(
    transaction: Transaction,
    client: Client,
    signers_count: Optional[int] = None,
) -> None:
    """
    Checks if the Transaction fee is higher than the expected Transaction type fee.

    Args:
        transaction: The transaction to check.
        client: Client instance to use to look up network load
        signers_count: the expected number of signers for this transaction.
            Only used for multisigned transactions.

    Raises:
        XRPLException: if the transaction fee is higher than the expected fee.
    """
    expected_fee = max(
        xrp_to_drops(0.1),  # a fee that is obviously too high
        await _calculate_fee_per_transaction_type(transaction, client, signers_count),
    )

    if transaction.fee and int(transaction.fee) > int(expected_fee):
        raise XRPLException(
            f"Fee value: {str(drops_to_xrp(transaction.fee))} XRP is likely entered "
            "incorrectly, since it is much larger than the typical XRP transaction "
            "cost. If this is intentional, use `check_fee=False`."
        )


async def _calculate_fee_per_transaction_type(
    transaction: Transaction,
    client: Client,
    signers_count: Optional[int] = None,
) -> str:
    """
    Calculate the total fee in drops for a transaction based on:
    - the network fee
    - the transaction condition

    https://xrpl.org/transaction-cost.html#special-transaction-costs

    Args:
        transaction: the Transaction to be submitted.
        client: the network client with which to submit the transaction.
        signers_count: the expected number of signers for this transaction.
            Only used for multisigned transactions.

    Returns:
        The expected Transaction fee in drops
    """
    # Reference Transaction (Most transactions)

    net_fee = int(
        await get_fee(client)
    )  # Latest data is found in FeeSettings ledger-object's BaseFee field.

    base_fee = net_fee

    # EscrowFinish Transaction with Fulfillment
    # https://xrpl.org/escrowfinish.html#escrowfinish-fields
    if transaction.transaction_type == TransactionType.ESCROW_FINISH:
        escrow_finish = cast(EscrowFinish, transaction)
        if escrow_finish.fulfillment is not None:
            fulfillment_bytes = escrow_finish.fulfillment.encode("ascii")
            # BaseFee × (33 + (Fulfillment size in bytes / 16))
            base_fee = math.ceil(net_fee * (33 + (len(fulfillment_bytes) / 16)))

    # AccountDelete Transaction
    if transaction.transaction_type in (
        TransactionType.ACCOUNT_DELETE,
        TransactionType.AMM_CREATE,
    ):
        base_fee = await _fetch_owner_reserve_fee(client)

    # Multi-signed Transaction
    # BaseFee × (1 + Number of Signatures Provided)
    if signers_count is not None and signers_count > 0:
        base_fee += net_fee * (1 + signers_count)
    # Round Up base_fee and return it as a String
    return str(math.ceil(base_fee))


async def _fetch_owner_reserve_fee(client: Client) -> int:
    server_state = await client._request_impl(ServerState())
    fee = server_state.result["state"]["validated_ledger"]["reserve_inc"]
    return int(fee)
