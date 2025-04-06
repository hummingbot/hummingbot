from abc import (
    ABC,
    abstractmethod,
)
import hashlib
import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from ckzg import (
    blob_to_kzg_commitment,
    compute_blob_kzg_proof,
    load_trusted_setup,
)
from eth_typing import (
    HexStr,
)
from eth_utils import (
    ValidationError,
    is_bytes,
    is_string,
    to_bytes,
    to_int,
)
from eth_utils.curried import (
    apply_formatter_to_array,
    apply_formatters_to_dict,
    apply_one_of_formatters,
    hexstr_if_str,
)
from eth_utils.toolz import (
    identity,
    merge,
)
from hexbytes import (
    HexBytes,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
    field_validator,
)

from eth_account._utils.validation import (
    LEGACY_TRANSACTION_FORMATTERS,
)

TYPED_TRANSACTION_FORMATTERS = merge(
    LEGACY_TRANSACTION_FORMATTERS,
    {
        "chainId": hexstr_if_str(to_int),
        "type": hexstr_if_str(to_int),
        "accessList": apply_formatter_to_array(
            apply_formatters_to_dict(
                {
                    "address": apply_one_of_formatters(
                        (
                            (is_string, hexstr_if_str(to_bytes)),
                            (is_bytes, identity),
                        )
                    ),
                    "storageKeys": apply_formatter_to_array(hexstr_if_str(to_int)),
                }
            ),
        ),
        "maxPriorityFeePerGas": hexstr_if_str(to_int),
        "maxFeePerGas": hexstr_if_str(to_int),
        "maxFeePerBlobGas": hexstr_if_str(to_int),
        "blobVersionedHashes": apply_formatter_to_array(hexstr_if_str(to_bytes)),
        "authorizationList": apply_formatter_to_array(
            apply_formatters_to_dict(
                {
                    "chainId": hexstr_if_str(to_int),
                    "nonce": hexstr_if_str(to_int),
                    "address": apply_one_of_formatters(
                        (
                            (is_string, hexstr_if_str(to_bytes)),
                            (is_bytes, identity),
                        )
                    ),
                    "yParity": hexstr_if_str(to_int),
                    "r": hexstr_if_str(to_int),
                    "s": hexstr_if_str(to_int),
                }
            ),
        ),
    },
)

# import TRUSTED_SETUP from ./kzg_trusted_setup.txt
TRUSTED_SETUP = os.path.join(
    os.path.dirname(__file__), "blob_transactions", "kzg_trusted_setup.txt"
)
VERSIONED_HASH_VERSION_KZG = b"\x01"


class _BlobDataElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    data: HexBytes

    def as_hexbytes(self) -> HexBytes:
        return self.data

    def as_bytes(self) -> bytes:
        return bytes(self.data)

    def as_hexstr(self) -> HexStr:
        return HexStr(f"0x{self.as_bytes().hex()}")


class Blob(_BlobDataElement):
    """
    Represents a Blob.
    """

    @field_validator("data")
    def validate_data(cls, v: Union[HexBytes, bytes]) -> Union[HexBytes, bytes]:
        if len(v) != 4096 * 32:
            raise ValidationError(
                "Invalid Blob size. Blob data must be comprised of 4096 32-byte "
                "field elements."
            )
        return v


class BlobKZGCommitment(_BlobDataElement):
    """
    Represents a Blob KZG Commitment.
    """

    @field_validator("data")
    def validate_commitment(cls, v: Union[HexBytes, bytes]) -> Union[HexBytes, bytes]:
        if len(v) != 48:
            raise ValidationError("Blob KZG Commitment must be 48 bytes long.")
        return v


class BlobProof(_BlobDataElement):
    """
    Represents a Blob Proof.
    """

    @field_validator("data")
    def validate_proof(cls, v: Union[HexBytes, bytes]) -> Union[HexBytes, bytes]:
        if len(v) != 48:
            raise ValidationError("Blob Proof must be 48 bytes long.")
        return v


class BlobVersionedHash(_BlobDataElement):
    """
    Represents a Blob Versioned Hash.
    """

    @field_validator("data")
    def validate_versioned_hash(
        cls, v: Union[HexBytes, bytes]
    ) -> Union[HexBytes, bytes]:
        if len(v) != 32:
            raise ValidationError("Blob Versioned Hash must be 32 bytes long.")
        if v[:1] != VERSIONED_HASH_VERSION_KZG:
            raise ValidationError(
                "Blob Versioned Hash must start with the KZG version byte."
            )
        return v


class BlobPooledTransactionData(BaseModel):
    """
    Represents the blob data for a type 3 `PooledTransaction` as defined by
    EIP-4844. This class takes blobs as bytes and computes the corresponding
    commitments, proofs, and versioned hashes.
    """

    _versioned_hash_version_kzg: bytes = VERSIONED_HASH_VERSION_KZG
    _versioned_hashes: Optional[List[BlobVersionedHash]] = None
    _commitments: Optional[List[BlobKZGCommitment]] = None
    _proofs: Optional[List[BlobProof]] = None

    blobs: List[Blob]

    def _kzg_to_versioned_hash(self, kzg_commitment: BlobKZGCommitment) -> bytes:
        return (
            self._versioned_hash_version_kzg
            + hashlib.sha256(kzg_commitment.data).digest()[1:]
        )

    @field_validator("blobs")
    def validate_blobs(cls, v: List[Blob]) -> List[Blob]:
        if len(v) == 0:
            raise ValidationError("Blob transactions must contain at least 1 blob.")
        elif len(v) > 6:
            raise ValidationError("Blob transactions cannot contain more than 6 blobs.")
        return v

    # type ignored bc mypy does not support decorated properties
    # https://github.com/python/mypy/issues/1362
    @computed_field  # type: ignore
    @property
    def versioned_hashes(self) -> List[BlobVersionedHash]:
        if self._versioned_hashes is None:
            self._versioned_hashes = [
                BlobVersionedHash(
                    data=HexBytes(self._kzg_to_versioned_hash(commitment))
                )
                for commitment in self.commitments
            ]
        return self._versioned_hashes

    # type ignored bc mypy does not support decorated properties
    # https://github.com/python/mypy/issues/1362
    @computed_field  # type: ignore
    @property
    def commitments(self) -> List[BlobKZGCommitment]:
        if self._commitments is None:
            self._commitments = [
                BlobKZGCommitment(
                    data=HexBytes(
                        blob_to_kzg_commitment(
                            blob.data, load_trusted_setup(TRUSTED_SETUP, 0)
                        )
                    )
                )
                for blob in self.blobs
            ]
        return self._commitments

    # type ignored bc mypy does not support decorated properties
    # https://github.com/python/mypy/issues/1362
    @computed_field  # type: ignore
    @property
    def proofs(self) -> List[BlobProof]:
        if self._proofs is None:
            self._proofs = [
                BlobProof(
                    data=HexBytes(
                        compute_blob_kzg_proof(
                            blob.data,
                            commitment.data,
                            load_trusted_setup(TRUSTED_SETUP, 0),
                        )
                    )
                )
                for blob, commitment in zip(self.blobs, self.commitments)
            ]
        return self._proofs


class _TypedTransactionImplementation(ABC):
    """
    Abstract class that every typed transaction must implement.
    Should not be imported or used by clients of the library.
    """

    blob_data: Optional[BlobPooledTransactionData] = None

    @abstractmethod
    def hash(self) -> bytes:
        pass

    @abstractmethod
    def payload(self) -> bytes:
        pass

    @abstractmethod
    def as_dict(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def vrs(self) -> Tuple[int, int, int]:
        pass
