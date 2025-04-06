from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
    cast,
)

from eth_rlp import (
    HashableRLP,
)
from eth_utils import (
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
    json_serialize_classes_in_transaction,
    set_transaction_type_if_needed,
    transaction_rlp_to_rpc_structure,
    transaction_rpc_to_rlp_structure,
)
from eth_account._utils.validation import (
    LEGACY_TRANSACTION_VALID_VALUES,
    is_int_or_prefixed_hexstr,
    is_rpc_structured_access_list,
    is_rpc_structured_authorization_list,
)
from eth_account.types import (
    Blobs,
)

from .access_list_transaction import (
    access_list_sede_type,
)
from .base import (
    TYPED_TRANSACTION_FORMATTERS,
    _TypedTransactionImplementation,
)


class Authorization(HashableRLP):
    magic = 5  # '0x05' 'MAGIC' as per specification EIP-7702
    fields = (
        ("chainId", big_endian_int),
        ("address", Binary.fixed_length(20, allow_empty=False)),
        ("nonce", big_endian_int),
    )

    def hash(self) -> HexBytes:
        """
        :returns: the hash of the encoded bytestring
        :rtype: ~hexbytes.main.HexBytes
        """
        return HexBytes(
            pipe(
                self,
                rlp.encode,
                lambda val: bytes([self.__class__.magic]) + val,  # (0x05 || rlp([...]))
                keccak,
            )
        )


class SignedAuthorization(HashableRLP):
    _authority: bytes

    fields = (
        ("chainId", big_endian_int),
        ("address", Binary.fixed_length(20, allow_empty=False)),
        ("nonce", big_endian_int),
        ("yParity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )


class SetCodeTransaction(_TypedTransactionImplementation):
    """
    Represents a set code transaction as per EIP-7702.
    """

    transaction_type = 4  # '0x04'

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
        ("authorizationList", CountableList(SignedAuthorization)),
    )

    signature_fields = (
        ("v", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )

    transaction_field_defaults = {
        "type": b"0x4",
        "chainId": 0,
        "nonce": 0,
        "to": b"",
        "value": 0,
        "data": b"",
        "accessList": [],
        "authorizationList": [],
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

    def __init__(self, dictionary: Dict[str, Any]):
        self.dictionary = dictionary

    @classmethod
    def assert_valid_fields(cls, dictionary: Dict[str, Any]) -> None:
        transaction_valid_values = merge(
            LEGACY_TRANSACTION_VALID_VALUES,
            {
                "type": is_int_or_prefixed_hexstr,
                "maxPriorityFeePerGas": is_int_or_prefixed_hexstr,
                "maxFeePerGas": is_int_or_prefixed_hexstr,
                "accessList": is_rpc_structured_access_list,
                "authorizationList": is_rpc_structured_authorization_list,
            },
        )

        if "v" in dictionary and dictionary["v"] == 0:
            # This is insane logic that is required because the way we evaluate
            # correct types is in the `if not all()` branch below, and 0 obviously
            # maps to the int(0), which maps to False... This was not an issue in
            # non-typed transaction because v=0, couldn't exist with the chain offset.
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
        cls, dictionary: Dict[str, Any], blobs: Optional[Blobs] = None
    ) -> "SetCodeTransaction":
        """
        Builds a SetCodeTransaction from a dictionary.
        Verifies that the dictionary is well-formed.
        """
        if blobs is not None:
            raise ValueError("Blob data is not supported for `SetCodeTransaction`.")

        dictionary = set_transaction_type_if_needed(dictionary)
        # pre-process any signed authorization pydantic models into dicts
        dictionary = json_serialize_classes_in_transaction(dictionary)

        # Validate fields.
        cls.assert_valid_fields(dictionary)
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
        return cls(dictionary=sanitized_dictionary)

    @classmethod
    def from_bytes(cls, encoded_transaction: HexBytes) -> "SetCodeTransaction":
        """Builds an SetCodeTransaction from a signed encoded transaction."""
        if not isinstance(encoded_transaction, HexBytes):
            raise TypeError(f"expected Hexbytes, got type: {type(encoded_transaction)}")
        if not (
            len(encoded_transaction) > 0
            and encoded_transaction[0] == cls.transaction_type
        ):
            raise ValueError("unexpected input")
        # Format is (0x04 || TransactionPayload)
        # We strip the prefix, and RLP unmarshal the payload into our
        # signed transaction serializer.
        transaction_payload = encoded_transaction[1:]
        rlp_serializer = cls._signed_transaction_serializer
        dictionary = rlp_serializer.from_bytes(transaction_payload).as_dict()  # type: ignore  # noqa: E501
        rpc_structured_dict = transaction_rlp_to_rpc_structure(dictionary)
        rpc_structured_dict["type"] = cls.transaction_type
        return cls.from_dict(rpc_structured_dict)

    def as_dict(self) -> Dict[str, Any]:
        """Returns this transaction as a dictionary."""
        dictionary = self.dictionary.copy()
        dictionary["type"] = self.__class__.transaction_type
        return dictionary

    def hash(self) -> bytes:
        """
        Hashes this SetCodeTransaction to prepare it for signing.
        As per the EIP-7702 specifications, the signature is a secp256k1 signature over
        ``keccak256(0x04 || rlp([chainId, nonce, max_priority_fee_per_gas,
        max_fee_per_gas, gasLimit, to, value, data, accessList, authorizationList])).``
        """
        # Remove signature fields.
        transaction_without_signature_fields = dissoc(self.dictionary, "v", "r", "s")
        # RPC-structured transaction to rlp-structured transaction
        rlp_structured_txn_without_sig_fields = transaction_rpc_to_rlp_structure(
            transaction_without_signature_fields
        )
        rlp_serializer = self.__class__._unsigned_transaction_serializer
        hash_ = pipe(
            rlp_serializer.from_dict(rlp_structured_txn_without_sig_fields),  # type: ignore  # noqa: E501
            lambda val: rlp.encode(val),  # rlp([...])
            lambda val: bytes([self.__class__.transaction_type])
            + val,  # (0x04 || rlp([...]))  # noqa: E501
            keccak,  # keccak256(0x04 || rlp([...]))
        )
        return cast(bytes, hash_)

    def payload(self) -> bytes:
        """
        Returns this transaction's payload as bytes.

        Here, the transaction payload is:

            TransactionPayload = rlp([chainId,
            nonce, maxPriorityFeePerGas, maxFeePerGas, gasLimit,
            to, value, data,
            accessList,
            authorizationsList,
            signatureYParity, signatureR, signatureS])
        """
        if not all(k in self.dictionary for k in "vrs"):
            raise ValueError("attempting to encode an unsigned transaction")
        rlp_serializer = self.__class__._signed_transaction_serializer
        rlp_structured_dict = transaction_rpc_to_rlp_structure(self.dictionary)
        payload = rlp.encode(rlp_serializer.from_dict(rlp_structured_dict))  # type: ignore  # noqa: E501
        return cast(bytes, payload)

    def vrs(self) -> Tuple[int, int, int]:
        """Returns (v, r, s) if they exist."""
        if not all(k in self.dictionary for k in "vrs"):
            raise ValueError("attempting to encode an unsigned transaction")
        return (self.dictionary["v"], self.dictionary["r"], self.dictionary["s"])
