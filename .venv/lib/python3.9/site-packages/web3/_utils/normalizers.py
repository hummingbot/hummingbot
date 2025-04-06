import codecs
import functools
import json
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Tuple,
    Union,
    cast,
)

from eth_abi.exceptions import (
    ParseError,
)
from eth_abi.grammar import (
    BasicType,
    parse,
)
from eth_typing import (
    ABI,
    ChecksumAddress,
    HexStr,
    TypeStr,
)
from eth_utils import (
    to_bytes,
    to_checksum_address,
    to_hex,
    to_text,
)
from eth_utils.address import (
    is_binary_address,
)
from eth_utils.toolz import (
    curry,
)
from hexbytes import (
    HexBytes,
)

from ens import (
    ENS,
    AsyncENS,
)
from web3._utils.encoding import (
    hexstr_if_str,
    text_if_str,
)
from web3._utils.ens import (
    StaticENS,
    async_validate_name_has_address,
    is_ens_name,
    validate_name_has_address,
)
from web3._utils.validation import (
    validate_abi,
    validate_address,
)
from web3.exceptions import (
    InvalidAddress,
    NameNotFound,
    Web3ValueError,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


def implicitly_identity(
    to_wrap: Callable[[TypeStr, Any], Any]
) -> Callable[[TypeStr, Any], Tuple[TypeStr, Any]]:
    @functools.wraps(to_wrap)
    def wrapper(type_str: TypeStr, data: Any) -> Tuple[TypeStr, Any]:
        modified = to_wrap(type_str, data)
        if modified is None:
            return type_str, data
        else:
            return modified

    return wrapper


#
# Return Normalizers
#


@implicitly_identity
def addresses_checksummed(
    type_str: TypeStr, data: Any
) -> Tuple[TypeStr, ChecksumAddress]:
    if type_str == "address":
        return type_str, to_checksum_address(data)
    return None


@implicitly_identity
def decode_abi_strings(type_str: TypeStr, data: Any) -> Tuple[TypeStr, str]:
    if type_str == "string":
        return type_str, codecs.decode(data, "utf8", "backslashreplace")
    return None


#
# Argument Normalizers
#


def parse_basic_type_str(
    old_normalizer: Callable[[BasicType, TypeStr, Any], Tuple[TypeStr, Any]]
) -> Callable[[TypeStr, Any], Tuple[TypeStr, Any]]:
    """
    Modifies a normalizer to automatically parse the incoming type string.  If
    that type string does not represent a basic type (i.e. non-tuple type) or is
    not parsable, the normalizer does nothing.
    """

    @functools.wraps(old_normalizer)
    def new_normalizer(type_str: TypeStr, data: Any) -> Tuple[TypeStr, Any]:
        try:
            abi_type = parse(type_str)
        except ParseError:
            # If type string is not parsable, do nothing
            return type_str, data

        if not isinstance(abi_type, BasicType):
            return type_str, data

        return old_normalizer(abi_type, type_str, data)

    return new_normalizer


@implicitly_identity
@parse_basic_type_str
def abi_bytes_to_hex(
    abi_type: BasicType, type_str: TypeStr, data: Any
) -> Optional[Tuple[TypeStr, HexStr]]:
    if abi_type.base != "bytes" or abi_type.is_array:
        return None

    bytes_data = hexstr_if_str(to_bytes, data)
    if abi_type.sub is None:
        return type_str, to_hex(bytes_data)

    num_bytes = abi_type.sub
    if len(bytes_data) > num_bytes:
        raise Web3ValueError(
            f"This value was expected to be at most {num_bytes} bytes, "
            f"but instead was {len(bytes_data)}: {data!r}"
        )

    padded = bytes_data.ljust(num_bytes, b"\0")
    return type_str, to_hex(padded)


@implicitly_identity
@parse_basic_type_str
def abi_int_to_hex(
    abi_type: BasicType, type_str: TypeStr, data: Any
) -> Optional[Tuple[TypeStr, HexStr]]:
    if abi_type.base == "uint" and not abi_type.is_array:
        # double check?
        return type_str, hexstr_if_str(to_hex, data)
    return None


@implicitly_identity
def abi_string_to_hex(type_str: TypeStr, data: Any) -> Optional[Tuple[TypeStr, str]]:
    if type_str == "string":
        return type_str, text_if_str(to_hex, data)
    return None


@implicitly_identity
def abi_string_to_text(type_str: TypeStr, data: Any) -> Optional[Tuple[TypeStr, str]]:
    if type_str == "string":
        return type_str, text_if_str(to_text, data)
    return None


@implicitly_identity
@parse_basic_type_str
def abi_bytes_to_bytes(
    abi_type: BasicType, type_str: TypeStr, data: Any
) -> Optional[Tuple[TypeStr, HexStr]]:
    if abi_type.base == "bytes" and not abi_type.is_array:
        return type_str, hexstr_if_str(to_bytes, data)
    return None


@implicitly_identity
def abi_address_to_hex(
    type_str: TypeStr, data: Any
) -> Optional[Tuple[TypeStr, ChecksumAddress]]:
    if type_str == "address":
        validate_address(data)
        if is_binary_address(data):
            return type_str, to_checksum_address(data)
    return None


@curry
def abi_ens_resolver(
    w3: "Web3",
    type_str: TypeStr,
    val: Any,
) -> Tuple[TypeStr, Any]:
    if type_str == "address" and is_ens_name(val):
        if w3 is None:
            raise InvalidAddress(
                f"Could not look up name {val!r} because no web3"
                " connection available"
            )

        _ens = cast(ENS, w3.ens)
        if _ens is None:
            raise InvalidAddress(
                f"Could not look up name {val!r} because ENS is set to None"
            )
        else:
            try:
                return type_str, validate_name_has_address(_ens, val)
            except NameNotFound as e:
                # TODO: This try/except is to keep backwards compatibility when we
                #  removed the mainnet requirement. Remove this in web3.py v7 and allow
                #  NameNotFound to raise.
                if not isinstance(_ens, StaticENS):
                    raise InvalidAddress(f"{e}")
                raise e
    else:
        return type_str, val


BASE_RETURN_NORMALIZERS = [
    addresses_checksummed,
]


#
# Property Normalizers
#


def normalize_abi(abi: Union[ABI, str]) -> ABI:
    if isinstance(abi, str):
        abi = json.loads(abi)
    validate_abi(cast(ABI, abi))
    return cast(ABI, abi)


def normalize_address(
    ens: ENS, address: Optional[ChecksumAddress]
) -> Union[ChecksumAddress, None]:
    if address:
        if is_ens_name(address):
            validate_name_has_address(ens, address)
        else:
            validate_address(address)
    return address


def normalize_address_no_ens(
    address: Optional[ChecksumAddress],
) -> Union[ChecksumAddress, None]:
    if address:
        validate_address(address)
    return address


def normalize_bytecode(bytecode: Optional[bytes]) -> Union[HexBytes, None]:
    if bytecode is not None:
        return HexBytes(bytecode)
    return bytecode


# --- async -- #


async def async_abi_ens_resolver(
    async_w3: "AsyncWeb3",
    type_str: TypeStr,
    val: Any,
) -> Tuple[TypeStr, Any]:
    if type_str == "address" and is_ens_name(val):
        if async_w3 is None:
            raise InvalidAddress(
                f"Could not look up name {val!r} because no web3"
                " connection available"
            )

        _async_ens = cast(AsyncENS, async_w3.ens)
        if _async_ens is None:
            raise InvalidAddress(
                f"Could not look up name {val!r} because ENS is set to None"
            )
        else:
            address = await async_validate_name_has_address(_async_ens, val)
            return type_str, address

    else:
        return type_str, val
