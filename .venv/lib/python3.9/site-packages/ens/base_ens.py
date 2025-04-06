from functools import (
    wraps,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Type,
    Union,
)

from eth_typing import (
    ChecksumAddress,
)
from eth_utils.abi import (
    get_abi_output_types,
)
from hexbytes import (
    HexBytes,
)

from .utils import (
    address_to_reverse_domain,
    is_valid_name,
    label_to_hash,
    normalize_name,
    raw_name_to_hash,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.contract import (  # noqa: F401
        AsyncContract,
        Contract,
    )


class BaseENS:
    w3: Union["AsyncWeb3", "Web3"] = None
    ens: Union["Contract", "AsyncContract"] = None
    _resolver_contract: Union[Type["Contract"], Type["AsyncContract"]] = None
    _reverse_resolver_contract: Union[Type["Contract"], Type["AsyncContract"]] = None

    @property
    def strict_bytes_type_checking(self) -> bool:
        return self.w3.strict_bytes_type_checking

    @strict_bytes_type_checking.setter
    def strict_bytes_type_checking(self, strict_bytes_type_check: bool) -> None:
        self.w3.strict_bytes_type_checking = strict_bytes_type_check

    @staticmethod
    @wraps(label_to_hash)
    def labelhash(label: str) -> HexBytes:
        return label_to_hash(label)

    @staticmethod
    @wraps(raw_name_to_hash)
    def namehash(name: str) -> HexBytes:
        return raw_name_to_hash(name)

    @staticmethod
    @wraps(normalize_name)
    def nameprep(name: str) -> str:
        return normalize_name(name)

    @staticmethod
    @wraps(is_valid_name)
    def is_valid_name(name: str) -> bool:
        return is_valid_name(name)

    @staticmethod
    @wraps(address_to_reverse_domain)
    def reverse_domain(address: ChecksumAddress) -> str:
        return address_to_reverse_domain(address)

    @staticmethod
    def parent(name: str) -> str:
        """
        Part of ENSIP-10. Returns the parent of a given ENS name,
        or the empty string if the ENS name does not have a parent.

        e.g.
        - parent('1.foo.bar.eth') = 'foo.bar.eth'
        - parent('foo.bar.eth') = 'bar.eth'
        - parent('foo.eth') = 'eth'
        - parent('eth') is defined as the empty string ''

        :param name: an ENS name
        :return: the parent for the provided ENS name
        :rtype: str
        """
        if not name:
            return ""

        labels = name.split(".")
        return "" if len(labels) == 1 else ".".join(labels[1:])

    def _decode_ensip10_resolve_data(
        self,
        contract_call_result: bytes,
        extended_resolver: Union["Contract", "AsyncContract"],
        fn_name: str,
    ) -> Any:
        # avoid getting 2 resolver functions named `addr`
        func = (
            extended_resolver.get_function_by_signature("addr(bytes32)")
            if fn_name == "addr"
            else extended_resolver.get_function_by_name(fn_name)
        )
        output_types = get_abi_output_types(func.abi)
        decoded = self.w3.codec.decode(output_types, contract_call_result)

        # if decoding a single value, return that value - else, return the tuple
        return decoded[0] if len(decoded) == 1 else decoded

    def _type_aware_resolver(
        self,
        address: ChecksumAddress,
        func: str,
    ) -> Union["Contract", "AsyncContract"]:
        return (
            self._reverse_resolver_contract(address=address)
            if func == "name"
            else self._resolver_contract(address=address)
        )
