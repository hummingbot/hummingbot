import itertools
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from eth_rlp import (
    HashableRLP,
)
from eth_utils.curried import (
    apply_formatters_to_dict,
)
from eth_utils.toolz import (
    curry,
    dissoc,
    merge,
    partial,
    pipe,
)
import rlp
from rlp.sedes import (
    Binary,
    big_endian_int,
    binary,
)

from eth_account.typed_transactions import (
    TypedTransaction,
)
from eth_account.types import (
    Blobs,
    TransactionDictType,
)

from .transaction_utils import (
    set_transaction_type_if_needed,
)
from .validation import (
    LEGACY_TRANSACTION_FORMATTERS,
    LEGACY_TRANSACTION_VALID_VALUES,
)

UNSIGNED_TRANSACTION_FIELDS = (
    ("nonce", big_endian_int),
    ("gasPrice", big_endian_int),
    ("gas", big_endian_int),
    ("to", Binary.fixed_length(20, allow_empty=True)),
    ("value", big_endian_int),
    ("data", binary),
)


class Transaction(HashableRLP):
    fields = UNSIGNED_TRANSACTION_FIELDS + (
        ("v", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )


class UnsignedTransaction(HashableRLP):
    fields = UNSIGNED_TRANSACTION_FIELDS


def serializable_unsigned_transaction_from_dict(
    transaction_dict: TransactionDictType, blobs: Optional[Blobs] = None
) -> Union[TypedTransaction, Transaction, UnsignedTransaction]:
    transaction_dict = set_transaction_type_if_needed(transaction_dict)
    if "type" in transaction_dict:
        # We delegate to TypedTransaction, which will carry out validation & formatting.
        return TypedTransaction.from_dict(transaction_dict, blobs=blobs)

    if blobs is not None:
        # sanity check, blobs should never get past typed transactions check above
        raise TypeError("Blob data is not supported for legacy transactions.")

    assert_valid_fields(transaction_dict)
    filled_transaction = pipe(
        transaction_dict,
        dict,
        partial(merge, TRANSACTION_DEFAULTS),
        chain_id_to_v,
        apply_formatters_to_dict(LEGACY_TRANSACTION_FORMATTERS),
    )
    if "v" in filled_transaction:
        serializer = Transaction
    else:
        serializer = UnsignedTransaction
    return serializer.from_dict(filled_transaction)


def encode_transaction(
    unsigned_transaction: Union[UnsignedTransaction, TypedTransaction],
    vrs: Tuple[int, int, int],
) -> bytes:
    (v, r, s) = vrs
    chain_naive_transaction = dissoc(unsigned_transaction.as_dict(), "v", "r", "s")
    if isinstance(unsigned_transaction, TypedTransaction):
        # Typed transaction have their own encoding format,
        # so we must delegate the encoding.
        chain_naive_transaction["v"] = v
        chain_naive_transaction["r"] = r
        chain_naive_transaction["s"] = s
        blob_data = unsigned_transaction.blob_data
        signed_typed_transaction = TypedTransaction.from_dict(
            chain_naive_transaction,
            blobs=[blob.as_bytes() for blob in blob_data.blobs] if blob_data else None,
        )
        return signed_typed_transaction.encode()

    signed_transaction = Transaction(v=v, r=r, s=s, **chain_naive_transaction)
    # type ignored because pyrlp is not typed
    return rlp.encode(signed_transaction)  # type: ignore[no-any-return]


TRANSACTION_DEFAULTS = {
    "to": b"",
    "value": 0,
    "data": b"",
    "chainId": None,
}

ALLOWED_TRANSACTION_KEYS = {
    "nonce",
    "gasPrice",
    "gas",
    "to",
    "value",
    "data",
    # set chainId to None if you want a transaction that can be replayed across networks
    "chainId",
}

REQUIRED_TRANSACTION_KEYS = ALLOWED_TRANSACTION_KEYS.difference(
    TRANSACTION_DEFAULTS.keys()
)


def assert_valid_fields(transaction_dict: TransactionDictType) -> None:
    # check if any keys are missing
    missing_keys = REQUIRED_TRANSACTION_KEYS.difference(transaction_dict.keys())
    if missing_keys:
        raise TypeError(f"Transaction must include these fields: {repr(missing_keys)}")

    # check if any extra keys were specified
    superfluous_keys = set(transaction_dict.keys()).difference(ALLOWED_TRANSACTION_KEYS)
    if superfluous_keys:
        raise TypeError(
            "Transaction must not include unrecognized fields: "
            f"{repr(superfluous_keys)}"
        )

    # check for valid types in each field
    valid_fields: Dict[str, bool]
    valid_fields = apply_formatters_to_dict(
        LEGACY_TRANSACTION_VALID_VALUES, transaction_dict
    )
    if not all(valid_fields.values()):
        invalid = {
            key: transaction_dict[key]
            for key, valid in valid_fields.items()
            if not valid
        }
        raise TypeError(f"Transaction had invalid fields: {repr(invalid)}")


def chain_id_to_v(transaction_dict: TransactionDictType) -> Dict[str, Any]:
    # See EIP 155
    chain_id = transaction_dict.pop("chainId")
    if chain_id is None:
        return transaction_dict
    else:
        return dict(transaction_dict, v=chain_id, r=0, s=0)


# type ignored because curry doesn't preserve typing
@curry  # type: ignore[misc]
def fill_transaction_defaults(
    transaction_dict: TransactionDictType,
) -> TransactionDictType:
    return cast(TransactionDictType, merge(TRANSACTION_DEFAULTS, transaction_dict))


ChainAwareUnsignedTransaction = Transaction


def strip_signature(transaction: Transaction) -> List[Union[int, bytes]]:
    unsigned_parts = itertools.islice(transaction, len(UNSIGNED_TRANSACTION_FIELDS))
    return list(unsigned_parts)


def vrs_from(transaction: Transaction) -> Generator[int, None, None]:
    return (getattr(transaction, part) for part in "vrs")
