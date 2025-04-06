# String encodings and numeric representations
import json
import re
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Optional,
    Sequence,
    Type,
    Union,
)

from eth_abi.encoding import (
    BaseArrayEncoder,
)
from eth_typing import (
    HexStr,
    Primitives,
    TypeStr,
)
from eth_utils import (
    add_0x_prefix,
    encode_hex,
    is_bytes,
    is_hex,
    is_list_like,
    remove_0x_prefix,
    to_bytes,
    to_hex,
)
from eth_utils.toolz import (
    curry,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.abi import (
    is_address_type,
    is_array_type,
    is_bool_type,
    is_bytes_type,
    is_int_type,
    is_string_type,
    is_uint_type,
    size_of_type,
    sub_type_of_array_type,
)
from web3._utils.validation import (
    validate_abi_type,
    validate_abi_value,
)
from web3.datastructures import (
    AttributeDict,
)
from web3.exceptions import (
    Web3TypeError,
    Web3ValueError,
)


def hex_encode_abi_type(
    abi_type: TypeStr, value: Any, force_size: Optional[int] = None
) -> HexStr:
    """
    Encodes value into a hex string in format of abi_type
    """
    validate_abi_type(abi_type)
    validate_abi_value(abi_type, value)

    data_size = force_size or size_of_type(abi_type)
    if is_array_type(abi_type):
        sub_type = sub_type_of_array_type(abi_type)
        return HexStr(
            "".join(
                [remove_0x_prefix(hex_encode_abi_type(sub_type, v, 256)) for v in value]
            )
        )
    elif is_bool_type(abi_type):
        return to_hex_with_size(value, data_size)
    elif is_uint_type(abi_type):
        return to_hex_with_size(value, data_size)
    elif is_int_type(abi_type):
        return to_hex_twos_compliment(value, data_size)
    elif is_address_type(abi_type):
        return pad_hex(value, data_size)
    elif is_bytes_type(abi_type):
        if is_bytes(value):
            return encode_hex(value)
        else:
            return value
    elif is_string_type(abi_type):
        return to_hex(text=value)
    else:
        raise Web3ValueError(f"Unsupported ABI type: {abi_type}")


def to_hex_twos_compliment(value: Any, bit_size: int) -> HexStr:
    """
    Converts integer value to twos compliment hex representation with given bit_size
    """
    if value >= 0:
        return to_hex_with_size(value, bit_size)

    value = (1 << bit_size) + value
    hex_value = hex(value)
    hex_value = HexStr(hex_value.rstrip("L"))
    return hex_value


def to_hex_with_size(value: Any, bit_size: int) -> HexStr:
    """
    Converts a value to hex with given bit_size:
    """
    return pad_hex(to_hex(value), bit_size)


def pad_hex(value: Any, bit_size: int) -> HexStr:
    """
    Pads a hex string up to the given bit_size
    """
    value = remove_0x_prefix(value)
    return add_0x_prefix(value.zfill(int(bit_size / 4)))


def trim_hex(hexstr: HexStr) -> HexStr:
    if hexstr.startswith("0x0"):
        hexstr = HexStr(re.sub("^0x0+", "0x", hexstr))
        if hexstr == "0x":
            hexstr = HexStr("0x0")
    return hexstr


@curry
def pad_bytes(fill_with: bytes, num_bytes: int, unpadded: bytes) -> bytes:
    return unpadded.rjust(num_bytes, fill_with)


zpad_bytes = pad_bytes(b"\0")


@curry
def text_if_str(
    to_type: Callable[..., str], text_or_primitive: Union[Primitives, HexStr, str]
) -> str:
    """
    Convert to a type, assuming that strings can be only unicode text (not a hexstr)

    @param to_type is a function that takes the arguments (primitive, hexstr=hexstr,
        text=text), eg~ to_bytes, to_text, to_hex, to_int, etc
    @param text_or_primitive in bytes, str, or int.
    """
    if isinstance(text_or_primitive, str):
        (primitive, text) = (None, text_or_primitive)
    else:
        (primitive, text) = (text_or_primitive, None)
    return to_type(primitive, text=text)


@curry
def hexstr_if_str(
    to_type: Callable[..., HexStr], hexstr_or_primitive: Union[Primitives, HexStr, str]
) -> HexStr:
    """
    Convert to a type, assuming that strings can be only hexstr (not unicode text)

    @param to_type is a function that takes the arguments (primitive, hexstr=hexstr,
        text=text), eg~ to_bytes, to_text, to_hex, to_int, etc
    @param hexstr_or_primitive in bytes, str, or int.
    """
    if isinstance(hexstr_or_primitive, str):
        (primitive, hexstr) = (None, hexstr_or_primitive)
        if remove_0x_prefix(HexStr(hexstr)) and not is_hex(hexstr):
            raise Web3ValueError(
                "when sending a str, it must be a hex string. "
                f"Got: {hexstr_or_primitive!r}"
            )
    else:
        (primitive, hexstr) = (hexstr_or_primitive, None)
    return to_type(primitive, hexstr=hexstr)


class FriendlyJsonSerde:
    """
    Friendly JSON serializer & deserializer

    When encoding or decoding fails, this class collects
    information on which fields failed, to show more
    helpful information in the raised error messages.
    """

    def _json_mapping_errors(self, mapping: Dict[Any, Any]) -> Iterable[str]:
        for key, val in mapping.items():
            try:
                self._friendly_json_encode(val)
            except TypeError as exc:
                yield f"{key!r}: because ({exc})"

    def _json_list_errors(self, iterable: Iterable[Any]) -> Iterable[str]:
        for index, element in enumerate(iterable):
            try:
                self._friendly_json_encode(element)
            except TypeError as exc:
                yield f"{index}: because ({exc})"

    def _friendly_json_encode(
        self, obj: Dict[Any, Any], cls: Optional[Type[json.JSONEncoder]] = None
    ) -> str:
        try:
            encoded = json.dumps(obj, cls=cls)
            return encoded
        except TypeError as full_exception:
            if hasattr(obj, "items"):
                item_errors = "; ".join(self._json_mapping_errors(obj))
                raise Web3TypeError(
                    f"dict had unencodable value at keys: {{{item_errors}}}"
                )
            elif is_list_like(obj):
                element_errors = "; ".join(self._json_list_errors(obj))
                raise Web3TypeError(
                    f"list had unencodable value at index: [{element_errors}]"
                )
            else:
                raise full_exception

    def json_decode(self, json_str: str) -> Dict[Any, Any]:
        try:
            decoded = json.loads(json_str)
            return decoded
        except json.decoder.JSONDecodeError as exc:
            err_msg = f"Could not decode {json_str!r} because of {exc}."
            # Calling code may rely on catching JSONDecodeError to recognize bad json
            # so we have to re-raise the same type.
            raise json.decoder.JSONDecodeError(err_msg, exc.doc, exc.pos)

    def json_encode(
        self, obj: Dict[Any, Any], cls: Optional[Type[json.JSONEncoder]] = None
    ) -> str:
        try:
            return self._friendly_json_encode(obj, cls=cls)
        except TypeError as exc:
            raise Web3TypeError(f"Could not encode to JSON: {exc}")


def to_4byte_hex(hex_or_str_or_bytes: Union[HexStr, str, bytes, int]) -> HexStr:
    size_of_4bytes = 4 * 8
    byte_str = hexstr_if_str(to_bytes, hex_or_str_or_bytes)
    if len(byte_str) > 4:
        raise Web3ValueError(
            f"expected value of size 4 bytes. Got: {len(byte_str)} bytes"
        )
    hex_str = encode_hex(byte_str)
    return pad_hex(hex_str, size_of_4bytes)


class DynamicArrayPackedEncoder(BaseArrayEncoder):
    is_dynamic = True

    def encode(self, value: Sequence[Any]) -> bytes:
        encoded_elements = self.encode_elements(value)  # type: ignore[no-untyped-call]
        encoded_value = encoded_elements

        return encoded_value


#  TODO: Replace with eth-abi packed encoder once web3 requires eth-abi>=2
def encode_single_packed(_type: TypeStr, value: Any) -> bytes:
    import codecs

    from eth_abi import (
        grammar as abi_type_parser,
    )
    from eth_abi.registry import (
        has_arrlist,
        registry,
    )

    abi_type = abi_type_parser.parse(_type)
    if has_arrlist(_type):  # type: ignore[no-untyped-call]
        item_encoder = registry.get_encoder(abi_type.item_type.to_type_str())
        if abi_type.arrlist[-1] != 1:
            return DynamicArrayPackedEncoder(item_encoder=item_encoder).encode(value)  # type: ignore[no-untyped-call]  # noqa: E501
        else:
            raise NotImplementedError(
                "Fixed arrays are not implemented in this packed encoder prototype"
            )
    elif abi_type.base == "string":
        return codecs.encode(value, "utf8")
    elif abi_type.base == "bytes":
        return value
    return None


class Web3JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Union[Dict[Any, Any], HexStr]:
        if isinstance(obj, AttributeDict):
            return obj.__dict__
        elif isinstance(obj, (HexBytes, bytes)):
            return to_hex(obj)
        return json.JSONEncoder.default(self, obj)


def to_json(obj: Dict[Any, Any]) -> str:
    """
    Convert a complex object (like a transaction object) to a JSON string
    """
    return FriendlyJsonSerde().json_encode(obj, cls=Web3JsonEncoder)
