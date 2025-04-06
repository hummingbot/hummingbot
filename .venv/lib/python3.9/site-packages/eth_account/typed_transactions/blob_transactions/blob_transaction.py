from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    cast,
)

from eth_rlp import (
    HashableRLP,
)
from eth_utils import (
    ValidationError,
    keccak,
)
from eth_utils.curried import (
    apply_formatters_to_dict,
)
from eth_utils.toolz import (
    dissoc,
    merge,
    partial,
    pipe,
)
from hexbytes import (
    HexBytes,
)
import rlp
from rlp.sedes import (
    Binary,
    CountableList,
    big_endian_int,
    binary,
)

from eth_account._utils.transaction_utils import (
    set_transaction_type_if_needed,
    transaction_rlp_to_rpc_structure,
    transaction_rpc_to_rlp_structure,
)
from eth_account._utils.validation import (
    LEGACY_TRANSACTION_VALID_VALUES,
    is_int_or_prefixed_hexstr,
    is_rpc_structured_access_list,
    is_sequence_of_bytes_or_hexstr,
)
from eth_account.typed_transactions.access_list_transaction import (
    access_list_sede_type,
)
from eth_account.typed_transactions.base import (
    TYPED_TRANSACTION_FORMATTERS,
    Blob,
    BlobPooledTransactionData,
    _TypedTransactionImplementation,
)
from eth_account.types import (
    Blobs,
)


class BlobTransaction(_TypedTransactionImplementation):
    """
    Represents a blob transaction as per EIP-4844.
    """

    transaction_type = 3  # '0x03'
    blob_data: Optional[BlobPooledTransactionData] = None

    unsigned_transaction_fields = (
        ("chainId", big_endian_int),
        ("nonce", big_endian_int),
        ("maxPriorityFeePerGas", big_endian_int),
        ("maxFeePerGas", big_endian_int),
        ("gas", big_endian_int),
        ("to", Binary.fixed_length(20, allow_empty=True)),
        ("value", big_endian_int),
        ("data", binary),
        ("accessList", access_list_sede_type),
        ("maxFeePerBlobGas", big_endian_int),
        (
            "blobVersionedHashes",
            CountableList(Binary.fixed_length(32, allow_empty=False)),
        ),
    )

    signature_fields = (
        ("v", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )

    transaction_field_defaults = {
        "type": b"0x3",
        "chainId": 0,
        "to": b"",
        "value": 0,
        "data": b"",
        "accessList": [],
    }

    _unsigned_transaction_serializer = type(
        "_unsigned_transaction_serializer",
        (HashableRLP,),
        {
            "fields": unsigned_transaction_fields,
        },
    )

    _signed_transaction_serializer = type(
        "_signed_transaction_serializer",
        (HashableRLP,),
        {
            "fields": unsigned_transaction_fields + signature_fields,
        },
    )

    _signed_pooled_transaction_serializer = type(
        "_signed_pooled_transaction_serializer",
        (HashableRLP,),
        {
            "fields": (
                ("tx_payload_body", _signed_transaction_serializer),
                (
                    "blobs",
                    CountableList(binary.fixed_length(4096 * 32)),
                ),
                (
                    "commitments",
                    CountableList(binary.fixed_length(48)),
                ),
                ("proofs", CountableList(binary.fixed_length(48))),
            ),
        },
    )

    def __init__(
        self,
        dictionary: Dict[str, Any],
        blobs: Optional[Blobs] = None,
    ):
        self.dictionary = dictionary

        if blobs is not None:
            self.blob_data = BlobPooledTransactionData(
                blobs=[Blob(data=HexBytes(blob_data)) for blob_data in blobs]
            )
            if "blobVersionedHashes" in dictionary:
                self._validate_versioned_hashes_against_blob_data(
                    dictionary["blobVersionedHashes"],
                    self.blob_data,
                )

    @classmethod
    def assert_valid_fields(
        cls,
        dictionary: Dict[str, Any],
        has_blobs: bool = False,
    ) -> None:
        transaction_valid_values = merge(
            LEGACY_TRANSACTION_VALID_VALUES,
            {
                "type": is_int_or_prefixed_hexstr,
                "maxPriorityFeePerGas": is_int_or_prefixed_hexstr,
                "maxFeePerGas": is_int_or_prefixed_hexstr,
                "accessList": is_rpc_structured_access_list,
                "maxFeePerBlobGas": is_int_or_prefixed_hexstr,
            },
        )
        if not has_blobs:
            transaction_valid_values[
                "blobVersionedHashes"
            ] = is_sequence_of_bytes_or_hexstr(item_bytes_size=32, can_be_empty=False)

        if "v" in dictionary and dictionary["v"] == 0:
            dictionary["v"] = "0x0"
        valid_fields = apply_formatters_to_dict(
            transaction_valid_values,
            dictionary,
        )  # type: Dict[str, Any]
        if not all(valid_fields.values()):
            invalid = {
                key: dictionary[key] for key, valid in valid_fields.items() if not valid
            }
            raise TypeError(f"Transaction had invalid fields: {repr(invalid)}")

    @classmethod
    def from_dict(
        cls,
        dictionary: Dict[str, Any],
        blobs: Optional[Blobs] = None,
    ) -> "BlobTransaction":
        """
        Builds a BlobTransaction from a dictionary.
        Verifies that the dictionary is well-formed.
        """
        has_blobs = blobs is not None

        if "tx_payload_body" in dictionary:
            dictionary = dict(
                zip(
                    (
                        entry[0]
                        for entry in cls.unsigned_transaction_fields
                        + cls.signature_fields
                    ),
                    dictionary["tx_payload_body"],
                )
            )
            dictionary["type"] = cls.transaction_type
        else:
            dictionary = set_transaction_type_if_needed(dictionary)

        # Validate fields.
        cls.assert_valid_fields(dictionary, has_blobs=has_blobs)
        sanitized_dictionary = pipe(
            dictionary,
            dict,
            partial(merge, cls.transaction_field_defaults),
            apply_formatters_to_dict(TYPED_TRANSACTION_FORMATTERS),
        )

        # We have verified the type, we can safely remove it from the dictionary,
        # given that it is not to be included within the RLP payload.
        transaction_type = sanitized_dictionary.pop("type")
        if transaction_type != cls.transaction_type:
            raise ValueError(
                f"expected transaction type {cls.transaction_type}, "
                f"got {transaction_type}"
            )
        return cls(
            dictionary=sanitized_dictionary,
            blobs=blobs,
        )

    @classmethod
    def from_bytes(cls, encoded_transaction: HexBytes) -> "BlobTransaction":
        """
        Builds a BlobTransaction from a signed encoded transaction.
        """
        if not isinstance(encoded_transaction, HexBytes):
            raise TypeError(f"expected Hexbytes, got type: {type(encoded_transaction)}")
        if not (
            len(encoded_transaction) > 0
            and encoded_transaction[0] == cls.transaction_type
        ):
            raise ValueError("unexpected input")

        # Format is (0x03 || TransactionPayload)
        # We strip the prefix, and RLP unmarshal the payload into our
        # signed transaction serializer.
        transaction_payload = encoded_transaction[1:]
        try:
            # Attempt to deserialize as a `PooledTransaction`, as defined in EIP-4844.
            dictionary = cls._signed_pooled_transaction_serializer.from_bytes(  # type: ignore  # noqa: E501
                transaction_payload
            ).as_dict()
        except rlp.exceptions.ObjectDeserializationError:
            # If the deserialization fails, we attempt to deserialize as a
            # `TransactionPayloadBody`, as defined in EIP-4844.
            dictionary = cls._signed_transaction_serializer.from_bytes(  # type: ignore  # noqa: E501
                transaction_payload
            ).as_dict()

        rpc_structured_dict = transaction_rlp_to_rpc_structure(dictionary)
        rpc_structured_dict["type"] = cls.transaction_type
        blobs = dictionary.get("blobs")
        return cls.from_dict(rpc_structured_dict, blobs=blobs)

    def as_dict(self) -> Dict[str, Any]:
        """Returns this transaction as a dictionary."""
        dictionary = self.dictionary.copy()
        dictionary["type"] = self.__class__.transaction_type

        if self.blob_data is not None:
            if "blobVersionedHashes" in dictionary:
                # we validate our versioned hashes calculation internally so this is a
                # safer way to ensure we're returning correct data.
                self._validate_versioned_hashes_against_blob_data(
                    dictionary["blobVersionedHashes"], self.blob_data
                )
            else:
                # If versioned hashes are not provided, we compute them.
                dictionary["blobVersionedHashes"] = [
                    versioned_hash.data
                    for versioned_hash in self.blob_data.versioned_hashes
                ]

        return dictionary

    def hash(self) -> bytes:
        """
        Keccak256 hash of the BlobTransaction to prepare it for signing.
        As per the EIP-4844 specifications, the signature is a secp256k1 signature over
        ``keccak256(0x03 || rlp([chainId, nonce, maxPriorityFeePerGas,
        maxFeePerGas, gasLimit, to, value, data, accessList, maxFeePerBlobGas,
        blobVersionedHashes]))``.
        """
        # Remove signature fields.
        transaction_without_signature_fields = dissoc(self.dictionary, "v", "r", "s")
        # RPC-structured transaction to rlp-structured transaction
        rlp_structured_txn_without_sig_fields = transaction_rpc_to_rlp_structure(
            transaction_without_signature_fields
        )

        if self.blob_data is not None:
            if rlp_structured_txn_without_sig_fields.get("blobVersionedHashes") is None:
                # If the versioned hashes are not provided, we compute them.
                rlp_structured_txn_without_sig_fields["blobVersionedHashes"] = [
                    versioned_hash.data
                    for versioned_hash in self.blob_data.versioned_hashes
                ]
            else:
                # Validate that the versioned hashes match the computed versioned
                # hashes.
                self._validate_versioned_hashes_against_blob_data(
                    rlp_structured_txn_without_sig_fields["blobVersionedHashes"],
                    self.blob_data,
                )

        rlp_serializer = self.__class__._unsigned_transaction_serializer
        hash_ = pipe(
            rlp_serializer.from_dict(rlp_structured_txn_without_sig_fields),  # type: ignore  # noqa: E501
            lambda val: rlp.encode(val),  # rlp([...])
            lambda val: bytes([self.__class__.transaction_type])
            + val,  # (0x03 || rlp([...]))
            keccak,  # keccak256(0x03 || rlp([...]))
        )
        return cast(bytes, hash_)

    def payload(self) -> bytes:
        """
        Returns this transaction's payload as bytes.

        Here, the transaction payload is:

            TransactionPayload = rlp([chainId,
            nonce, maxPriorityFeePerGas, maxFeePerGas, gasLimit, to, value, data,
            accessList, maxFeePerBlobGas, blobVersionedHashes, signatureYParity,
            signatureR, signatureS])

        """
        if not all(k in self.dictionary for k in "vrs"):
            raise ValueError("attempting to encode an unsigned transaction")

        rlp_structured_dict = transaction_rpc_to_rlp_structure(self.dictionary)
        if self.blob_data is None:
            # `TransactionPayload` as defined in EIP-4844
            # rlp([tx_payload_body])
            rlp_serializer = self.__class__._signed_transaction_serializer
            payload = rlp.encode(rlp_serializer.from_dict(rlp_structured_dict))  # type: ignore # noqa: E501
        else:
            # `PooledTransaction` as defined in EIP-4844
            # rlp([tx_payload_body, blobs, commitments, proofs])
            rlp_serializer = self.__class__._signed_pooled_transaction_serializer
            pooled_txn_as_dict = {
                "tx_payload_body": tuple(
                    rlp_structured_dict[key]
                    for key, _val in (
                        self.unsigned_transaction_fields + self.signature_fields
                    )
                ),
                "blobs": [blob.as_bytes() for blob in self.blob_data.blobs],
                "commitments": [
                    commitment.as_bytes() for commitment in self.blob_data.commitments
                ],
                "proofs": [proof.as_bytes() for proof in self.blob_data.proofs],
            }
            payload = rlp.encode(rlp_serializer.from_dict(pooled_txn_as_dict))  # type: ignore # noqa: E501

        return cast(bytes, payload)

    def vrs(self) -> Tuple[int, int, int]:
        """Returns (v, r, s) if they exist."""
        if not all(k in self.dictionary for k in "vrs"):
            raise ValueError("attempting to encode an unsigned transaction")
        return (self.dictionary["v"], self.dictionary["r"], self.dictionary["s"])

    @staticmethod
    def _validate_versioned_hashes_against_blob_data(
        blob_versioned_hashes: List[bytes],
        blob_data: BlobPooledTransactionData,
    ) -> None:
        diff = set(blob_versioned_hashes).difference(
            {versioned_hash.data for versioned_hash in blob_data.versioned_hashes}
        )
        if diff:
            raise ValidationError(
                "`blobVersionedHashes` value defined in transaction does not match "
                f"versioned hashes computed from blobs.\n    diff: {diff}"
            )
