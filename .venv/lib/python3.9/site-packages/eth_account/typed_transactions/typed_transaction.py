from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
    Union,
)

from eth_utils.curried import (
    hexstr_if_str,
    to_int,
)
from eth_utils.toolz import (
    pipe,
)
from hexbytes import (
    HexBytes,
)

from eth_account._utils.transaction_utils import (
    normalize_transaction_dict,
    set_transaction_type_if_needed,
)
from eth_account._utils.validation import (
    is_int_or_prefixed_hexstr,
)
from eth_account.types import (
    Blobs,
)

from .access_list_transaction import (
    AccessListTransaction,
)
from .base import (
    _TypedTransactionImplementation,
)
from .blob_transactions.blob_transaction import (
    BlobPooledTransactionData,
    BlobTransaction,
)
from .dynamic_fee_transaction import (
    DynamicFeeTransaction,
)
from .set_code_transaction import (
    SetCodeTransaction,
)


class TypedTransaction:
    """
    Represents a Typed Transaction as per EIP-2718.
    The currently supported Transaction Types are:

     * EIP-2930's AccessListTransaction
     * EIP-1559's DynamicFeeTransaction
     * EIP-4844's BlobTransaction
     * EIP-7702's SetCodeTransaction

    """

    def __init__(
        self, transaction_type: int, transaction: _TypedTransactionImplementation
    ):
        """Should not be called directly. Use instead the 'from_dict' method."""
        if not isinstance(transaction, _TypedTransactionImplementation):
            raise TypeError(
                f"expected _TypedTransactionImplementation, got {type(transaction)}"
            )
        if not isinstance(transaction_type, int):
            raise TypeError(f"expected int, got {type(transaction_type)}")
        self.transaction_type = transaction_type
        self.transaction = transaction

    @property
    def blob_data(self) -> Optional[BlobPooledTransactionData]:
        """Returns the blobs associated with this transaction."""
        return self.transaction.blob_data

    @classmethod
    def from_dict(
        cls, dictionary: Dict[str, Any], blobs: Optional[Blobs] = None
    ) -> "TypedTransaction":
        """
        Builds a TypedTransaction from a dictionary.
        Verifies the dictionary is well formed.
        """
        dictionary = set_transaction_type_if_needed(dictionary)
        if not ("type" in dictionary and is_int_or_prefixed_hexstr(dictionary["type"])):
            raise ValueError("missing or incorrect transaction type")
        # Switch on the transaction type to choose the correct constructor.
        transaction_type = pipe(dictionary["type"], hexstr_if_str(to_int))
        transaction: Any

        if transaction_type == AccessListTransaction.transaction_type:
            transaction = AccessListTransaction
        elif transaction_type == DynamicFeeTransaction.transaction_type:
            transaction = DynamicFeeTransaction
        elif transaction_type == BlobTransaction.transaction_type:
            transaction = BlobTransaction
        elif transaction_type == SetCodeTransaction.transaction_type:
            transaction = SetCodeTransaction
        else:
            raise TypeError(f"Unknown Transaction type: {transaction_type}")
        return cls(
            transaction_type=transaction_type,
            transaction=transaction.from_dict(dictionary, blobs=blobs),
        )

    @classmethod
    def from_bytes(cls, encoded_transaction: HexBytes) -> "TypedTransaction":
        """Builds a TypedTransaction from a signed encoded transaction."""
        if not isinstance(encoded_transaction, HexBytes):
            raise TypeError(f"expected Hexbytes, got {type(encoded_transaction)}")
        if not (len(encoded_transaction) > 0 and encoded_transaction[0] <= 0x7F):
            raise ValueError("unexpected input")

        transaction: Union[
            "DynamicFeeTransaction",
            "AccessListTransaction",
            "BlobTransaction",
            "SetCodeTransaction",
        ]

        encoded_tx_type = encoded_transaction[0]
        if encoded_tx_type == AccessListTransaction.transaction_type:
            transaction_type = AccessListTransaction.transaction_type
            transaction = AccessListTransaction.from_bytes(encoded_transaction)
        elif encoded_tx_type == DynamicFeeTransaction.transaction_type:
            transaction_type = DynamicFeeTransaction.transaction_type
            transaction = DynamicFeeTransaction.from_bytes(encoded_transaction)
        elif encoded_tx_type == BlobTransaction.transaction_type:
            transaction_type = BlobTransaction.transaction_type
            transaction = BlobTransaction.from_bytes(encoded_transaction)
        elif encoded_tx_type == SetCodeTransaction.transaction_type:
            transaction_type = SetCodeTransaction.transaction_type
            transaction = SetCodeTransaction.from_bytes(encoded_transaction)
        else:
            # The only known transaction types should be explicit if/elif branches.
            raise TypeError(
                f"typed transaction has unknown type: {encoded_transaction[0]}"
            )
        return cls(
            transaction_type=transaction_type,
            transaction=transaction,
        )

    def hash(self) -> bytes:
        """
        Hashes this TypedTransaction to prepare it for signing.

        As per the EIP-2718 specifications,
        the hashing format is dictated by the transaction type itself,
        and so we delegate the call.
        Note that the return type will be bytes.
        """
        return self.transaction.hash()

    def encode(self) -> bytes:
        """
        Encodes this TypedTransaction and returns it as bytes.

        The transaction format follows EIP-2718's typed transaction
        format (TransactionType || TransactionPayload).
        Note that we delegate to a transaction type's payload() method as
        the EIP-2718 does not prescribe a TransactionPayload format,
        leaving types free to implement their own encoding.
        """
        return bytes([self.transaction_type]) + self.transaction.payload()

    def as_dict(self) -> Dict[str, Any]:
        """Returns this transaction as a dictionary."""
        return normalize_transaction_dict(self.transaction.as_dict())

    def vrs(self) -> Tuple[int, int, int]:
        """Returns (v, r, s) if they exist."""
        return self.transaction.vrs()
