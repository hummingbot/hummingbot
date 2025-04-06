from datetime import (
    datetime,
    timezone,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Collection,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from eth_typing import (
    Address,
    ChecksumAddress,
    HexAddress,
    HexStr,
)
from eth_utils import (
    is_same_address,
    remove_0x_prefix,
    to_bytes,
    to_normalized_address,
)
from hexbytes import (
    HexBytes,
)

from ens.exceptions import (
    ENSTypeError,
    ENSValueError,
)

from .constants import (
    ACCEPTABLE_STALE_HOURS,
    AUCTION_START_GAS_CONSTANT,
    AUCTION_START_GAS_MARGINAL,
    EMPTY_ADDR_HEX,
    EMPTY_SHA3_BYTES,
    REVERSE_REGISTRAR_DOMAIN,
)
from .exceptions import (
    ENSValidationError,
    InvalidName,
)

default = object()


if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3 as _Web3,
    )
    from web3.middleware.base import (
        Middleware,
    )
    from web3.providers import (  # noqa: F401
        AsyncBaseProvider,
        BaseProvider,
    )


def Web3() -> Type["_Web3"]:
    from web3 import (
        Web3 as Web3Main,
    )

    return Web3Main


def init_web3(
    provider: "BaseProvider" = None,
    middleware: Optional[Sequence[Tuple["Middleware", str]]] = None,
) -> "_Web3":
    from web3 import (
        Web3 as Web3Main,
    )
    from web3.eth import (
        Eth as EthMain,
    )

    provider = provider or cast("BaseProvider", default)
    if provider is default:
        w3 = Web3Main(ens=None, modules={"eth": (EthMain)})
    else:
        w3 = Web3Main(provider, middleware, ens=None, modules={"eth": (EthMain)})

    return customize_web3(w3)


def customize_web3(w3: "_Web3") -> "_Web3":
    from web3.middleware import (
        StalecheckMiddlewareBuilder,
    )

    if w3.middleware_onion.get("ens_name_to_address"):
        w3.middleware_onion.remove("ens_name_to_address")

    if not w3.middleware_onion.get("stalecheck"):
        stalecheck_middleware = StalecheckMiddlewareBuilder.build(
            ACCEPTABLE_STALE_HOURS * 3600
        )
        w3.middleware_onion.add(stalecheck_middleware, name="stalecheck")
    return w3


def normalize_name(name: str) -> str:
    """
    Clean the fully qualified name, as defined in ENS `EIP-137
    <https://github.com/ethereum/EIPs/blob/master/EIPS/eip-137.md#name-syntax>`_  # blocklint: pragma # noqa: E501

    This does *not* enforce whether ``name`` is a label or fully qualified domain.

    :param str name: the dot-separated ENS name
    :raises InvalidName: if ``name`` has invalid syntax
    """
    # Defer import because module initialization takes > 0.1 ms
    from ._normalization import (
        normalize_name_ensip15,
    )

    if is_empty_name(name):
        return ""
    elif isinstance(name, (bytes, bytearray)):
        name = name.decode("utf-8")

    return normalize_name_ensip15(name).as_text


def ens_encode_name(name: str) -> bytes:
    r"""
    Encode a name according to DNS standards specified in section 3.1
    of RFC1035 with the following validations:

        - There is no limit on the total length of the encoded name
        and the limit on labels is the ENS standard of 255.

        - Return a single 0-octet, b'\x00', if empty name.

    :param str name: the dot-separated ENS name
    """
    if is_empty_name(name):
        return b"\x00"

    normalized_name = normalize_name(name)

    labels = normalized_name.split(".")
    labels_as_bytes = [to_bytes(text=label) for label in labels]

    # raises if len(label) > 255:
    for index, label in enumerate(labels):
        if len(label) > 255:
            raise ENSValidationError(
                f"Label at position {index} too long after encoding."
            )

    # concat label size in bytes to each label:
    dns_prepped_labels = [to_bytes(len(label)) + label for label in labels_as_bytes]

    # return the joined prepped labels in order and append the zero byte at the end:
    return b"".join(dns_prepped_labels) + b"\x00"


def is_valid_name(name: str) -> bool:
    """
    Validate whether the fully qualified name is valid, as defined in ENS `EIP-137
    <https://github.com/ethereum/EIPs/blob/master/EIPS/eip-137.md#name-syntax>`_  # blocklint: pragma # noqa: E501

    :param str name: the dot-separated ENS name
    :returns: True if ``name`` is set, and :meth:`~ens.ENS.nameprep` will not
              raise InvalidName
    """
    if is_empty_name(name):
        return False
    try:
        normalize_name(name)
        return True
    except InvalidName:
        return False


def to_utc_datetime(timestamp: float) -> Optional[datetime]:
    return datetime.fromtimestamp(timestamp, timezone.utc) if timestamp else None


def sha3_text(val: Union[str, bytes]) -> HexBytes:
    if isinstance(val, str):
        val = val.encode("utf-8")
    return Web3().keccak(val)


def label_to_hash(label: str) -> HexBytes:
    label = normalize_name(label)
    if "." in label:
        raise ENSValueError(f"Cannot generate hash for label {label!r} with a '.'")
    return Web3().keccak(text=label)


def normal_name_to_hash(name: str) -> HexBytes:
    """
    Hashes a pre-normalized name.
    The normalization of the name is a prerequisite and is not handled by this function.

    :param str name: A normalized name string to be hashed.
    :return: namehash - the hash of the name
    :rtype: HexBytes
    """
    node = EMPTY_SHA3_BYTES
    if not is_empty_name(name):
        labels = name.split(".")
        for label in reversed(labels):
            labelhash = label_to_hash(label)
            assert isinstance(labelhash, bytes)
            assert isinstance(node, bytes)
            node = Web3().keccak(node + labelhash)
    return node


def raw_name_to_hash(name: str) -> HexBytes:
    """
    Generate the namehash. This is also known as the ``node`` in ENS contracts.

    In normal operation, generating the namehash is handled
    behind the scenes. For advanced usage, it is a helpful utility.

    This normalizes the name with `nameprep
    <https://github.com/ethereum/EIPs/blob/master/EIPS/eip-137.md#name-syntax>`_  # blocklint: pragma # noqa: E501
    before hashing.

    :param str name: ENS name to hash
    :return: the namehash
    :rtype: bytes
    :raises InvalidName: if ``name`` has invalid syntax
    """
    normalized_name = normalize_name(name)
    return normal_name_to_hash(normalized_name)


def address_in(
    address: ChecksumAddress, addresses: Collection[ChecksumAddress]
) -> bool:
    return any(is_same_address(address, item) for item in addresses)


def address_to_reverse_domain(address: ChecksumAddress) -> str:
    lower_unprefixed_address = remove_0x_prefix(HexStr(to_normalized_address(address)))
    return lower_unprefixed_address + "." + REVERSE_REGISTRAR_DOMAIN


def estimate_auction_start_gas(labels: Collection[str]) -> int:
    return AUCTION_START_GAS_CONSTANT + AUCTION_START_GAS_MARGINAL * len(labels)


def assert_signer_in_modifier_kwargs(modifier_kwargs: Any) -> ChecksumAddress:
    ERR_MSG = "You must specify the sending account"
    assert len(modifier_kwargs) == 1, ERR_MSG

    _modifier_type, modifier_dict = dict(modifier_kwargs).popitem()
    if "from" not in modifier_dict:
        raise ENSTypeError(ERR_MSG)

    return modifier_dict["from"]


def is_none_or_zero_address(addr: Union[Address, ChecksumAddress, HexAddress]) -> bool:
    return not addr or addr == EMPTY_ADDR_HEX


def is_empty_name(name: str) -> bool:
    return name is None or name.strip() in {"", "."}


def is_valid_ens_name(ens_name: str) -> bool:
    split_domain = ens_name.split(".")
    if len(split_domain) == 1:
        return False
    for name in split_domain:
        if not is_valid_name(name):
            return False
    return True


# -- async -- #


def init_async_web3(
    provider: "AsyncBaseProvider" = None,
    middleware: Optional[Sequence[Tuple["Middleware", str]]] = (),
) -> "AsyncWeb3":
    from web3 import (
        AsyncWeb3 as AsyncWeb3Main,
    )
    from web3.eth import (
        AsyncEth as AsyncEthMain,
    )
    from web3.middleware import (
        StalecheckMiddlewareBuilder,
    )

    provider = provider or cast("AsyncBaseProvider", default)
    middleware = list(middleware)
    for i, (_mw, name) in enumerate(middleware):
        if name == "ens_name_to_address":
            middleware.pop(i)

    if "stalecheck" not in (name for mw, name in middleware):
        middleware.append(
            (
                StalecheckMiddlewareBuilder.build(ACCEPTABLE_STALE_HOURS * 3600),
                "stalecheck",
            )
        )

    if provider is default:
        async_w3 = AsyncWeb3Main(
            middleware=middleware, ens=None, modules={"eth": (AsyncEthMain)}
        )
    else:
        async_w3 = AsyncWeb3Main(
            provider,
            middleware=middleware,
            ens=None,
            modules={"eth": (AsyncEthMain)},
        )

    return async_w3
