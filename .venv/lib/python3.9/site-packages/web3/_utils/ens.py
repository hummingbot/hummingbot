from contextlib import (
    contextmanager,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    Union,
    cast,
)

from eth_typing import (
    ChecksumAddress,
)
from eth_utils import (
    is_0x_prefixed,
    is_hex,
    is_hex_address,
    to_checksum_address,
)

from ens import (
    ENS,
    AsyncENS,
)
from web3.exceptions import (
    NameNotFound,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.contract import (  # noqa: F401
        Contract,
    )


def is_ens_name(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    elif is_hex_address(value):
        return False
    elif is_0x_prefixed(value) and is_hex(value):
        return False
    else:
        return ENS.is_valid_name(value)


def validate_name_has_address(ens: ENS, name: str) -> ChecksumAddress:
    addr = ens.address(name)
    if addr:
        return to_checksum_address(addr)
    else:
        raise NameNotFound(f"Could not find address for name {name!r}")


class StaticENS:
    def __init__(self, name_addr_pairs: Dict[str, ChecksumAddress]) -> None:
        self.registry = dict(name_addr_pairs)

    def address(self, name: str) -> ChecksumAddress:
        return self.registry.get(name, None)


@contextmanager
def ens_addresses(
    w3: Union["Web3", "AsyncWeb3"], name_addr_pairs: Dict[str, ChecksumAddress]
) -> Iterator[None]:
    original_ens = w3.ens
    if w3.provider.is_async:
        w3.ens = cast(AsyncENS, StaticENS(name_addr_pairs))
    else:
        w3.ens = cast(ENS, StaticENS(name_addr_pairs))
    yield
    w3.ens = original_ens


@contextmanager
def contract_ens_addresses(
    contract: "Contract", name_addr_pairs: Dict[str, ChecksumAddress]
) -> Iterator[None]:
    """
    Use this context manager to temporarily resolve name/address pairs
    supplied as the argument. For example:

    with contract_ens_addresses(mycontract, [('resolve-as-1s.eth', '0x111...111')]):
        # any contract call or transaction in here would only resolve the above ENS pair
    """
    with ens_addresses(contract.w3, name_addr_pairs):
        yield


# --- async --- #


async def async_validate_name_has_address(
    async_ens: AsyncENS, name: str
) -> ChecksumAddress:
    addr = await async_ens.address(name)
    if not addr:
        raise NameNotFound(f"Could not find address for name {name!r}")
    return addr
