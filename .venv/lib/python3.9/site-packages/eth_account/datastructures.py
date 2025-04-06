from typing import (
    Any,
    NamedTuple,
    Set,
    SupportsIndex,
    Tuple,
    Union,
    overload,
)

from eth_keys.datatypes import (
    Signature,
)
from eth_typing import (
    ChecksumAddress,
)
from eth_utils import (
    to_checksum_address,
)
from hexbytes import (
    HexBytes,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
)
from pydantic.alias_generators import (
    to_camel,
)


class SignedTransaction(
    NamedTuple(
        "SignedTransaction",
        [
            ("raw_transaction", HexBytes),
            ("hash", HexBytes),
            ("r", int),
            ("s", int),
            ("v", int),
        ],
    )
):
    @overload
    def __getitem__(self, index: SupportsIndex) -> Any:
        ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[Any, ...]:
        ...

    @overload
    def __getitem__(self, index: str) -> Any:
        ...

    def __getitem__(self, index: Union[SupportsIndex, slice, str]) -> Any:
        if isinstance(index, (int, slice)):
            return super().__getitem__(index)
        elif isinstance(index, str):
            return getattr(self, index)
        else:
            raise TypeError("Index must be an integer, slice, or string")


class SignedMessage(
    NamedTuple(
        "SignedMessage",
        [
            ("message_hash", HexBytes),
            ("r", int),
            ("s", int),
            ("v", int),
            ("signature", HexBytes),
        ],
    )
):
    @overload
    def __getitem__(self, index: SupportsIndex) -> Any:
        ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[Any, ...]:
        ...

    @overload
    def __getitem__(self, index: str) -> Any:
        ...

    def __getitem__(self, index: Union[SupportsIndex, slice, str]) -> Any:
        if isinstance(index, (int, slice)):
            return super().__getitem__(index)
        elif isinstance(index, str):
            return getattr(self, index)
        else:
            raise TypeError("Index must be an integer, slice, or string")


class CustomPydanticModel(BaseModel):
    """
    Classes inheriting from this base model need only define any excluded fields as
    ``_exclude: Set[str]``. This base class includes the instructions for how nested
    pydantic models should be json-serialized.
    """

    _exclude: Set[str] = set()

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    def recursive_model_dump(self) -> Any:
        """
        Recursively serialize the model, respecting nested `_exclude` fields.
        """
        output = {}
        for field_name, field_value in self:
            if field_name in self._exclude:
                continue
            elif isinstance(field_value, CustomPydanticModel):
                output_key = self.model_fields[field_name].alias
                output[output_key] = field_value.recursive_model_dump()
            elif isinstance(field_value, list):
                output_key = self.model_fields[field_name].alias
                output[output_key] = [
                    (
                        item.recursive_model_dump()
                        if isinstance(item, CustomPydanticModel)
                        else item
                    )
                    for item in field_value
                ]
            else:
                output_key = self.model_fields[field_name].alias
                serializer = getattr(self, f"serialize_{field_name}", None)
                if serializer:
                    if hasattr(serializer, "wrapped"):
                        output[output_key] = serializer.wrapped(serializer, field_value)
                    else:
                        output[output_key] = serializer(field_value)
                else:
                    output[output_key] = field_value

        return output


class SignedSetCodeAuthorization(CustomPydanticModel):
    chain_id: int
    address: bytes
    nonce: int
    y_parity: int
    r: int
    s: int
    signature: Signature
    authorization_hash: HexBytes

    _exclude = {"signature", "authorization_hash", "authority"}

    @classmethod
    @field_serializer("address")
    def serialize_address(cls, value: bytes) -> ChecksumAddress:
        return to_checksum_address(value)

    @property
    def authority(self) -> bytes:
        """
        Return the address of the authority that signed the authorization.

        In order to prevent any potential confusion or mal-intent, the authority is
        always derived from the signature and the authorization hash, rather than
        statically assigned. This value should be verified against the expected
        authority for a signed authorization.
        """
        return self.signature.recover_public_key_from_msg_hash(
            self.authorization_hash
        ).to_canonical_address()
