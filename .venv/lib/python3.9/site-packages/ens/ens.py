from copy import (
    deepcopy,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Sequence,
    Tuple,
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
    is_address,
    is_binary_address,
    is_checksum_address,
    to_checksum_address,
)
from eth_utils.toolz import (
    merge,
)
from hexbytes import (
    HexBytes,
)

from . import (
    abis,
)
from .base_ens import (
    BaseENS,
)
from .constants import (
    EMPTY_ADDR_HEX,
    ENS_EXTENDED_RESOLVER_INTERFACE_ID,
    ENS_MAINNET_ADDR,
    ENS_MULTICHAIN_ADDRESS_INTERFACE_ID,
    ENS_TEXT_INTERFACE_ID,
    REVERSE_REGISTRAR_DOMAIN,
)
from .exceptions import (
    AddressMismatch,
    ENSValueError,
    ResolverNotFound,
    UnauthorizedError,
    UnownedName,
    UnsupportedFunction,
)
from .utils import (
    address_in,
    address_to_reverse_domain,
    default,
    ens_encode_name,
    init_web3,
    is_empty_name,
    is_none_or_zero_address,
    label_to_hash,
    normal_name_to_hash,
    normalize_name,
    raw_name_to_hash,
)

if TYPE_CHECKING:
    from web3 import Web3  # noqa: F401
    from web3.contract.contract import (  # noqa: F401
        Contract,
        ContractFunction,
    )
    from web3.middleware.base import (  # noqa: F401
        Middleware,
    )
    from web3.providers import (  # noqa: F401
        BaseProvider,
    )
    from web3.types import (  # noqa: F401
        TxParams,
    )


class ENS(BaseENS):
    """
    Quick access to common Ethereum Name Service functions,
    like getting the address for a name.

    Unless otherwise specified, all addresses are assumed to be a `str` in
    `checksum format <https://github.com/ethereum/EIPs/blob/master/EIPS/eip-155.md>`_,  # blocklint: pragma # noqa: E501
    like: ``"0x314159265dD8dbb310642f98f50C066173C1259b"``
    """

    # mypy types
    w3: "Web3"

    def __init__(
        self,
        provider: "BaseProvider" = None,
        addr: ChecksumAddress = None,
        middleware: Optional[Sequence[Tuple["Middleware", str]]] = None,
    ) -> None:
        """
        :param provider: a single provider used to connect to Ethereum
        :type provider: instance of `web3.providers.base.BaseProvider`
        :param hex-string addr: the address of the ENS registry on-chain.
            If not provided, ENS.py will default to the mainnet ENS
            registry address.
        """
        provider = provider or cast("BaseProvider", default)
        self.w3 = init_web3(provider, middleware)

        ens_addr = addr if addr else ENS_MAINNET_ADDR
        self.ens = self.w3.eth.contract(abi=abis.ENS, address=ens_addr)
        self._resolver_contract = self.w3.eth.contract(
            abi=abis.PUBLIC_RESOLVER_2_EXTENDED
        )
        self._reverse_resolver_contract = self.w3.eth.contract(
            abi=abis.REVERSE_RESOLVER
        )

    @classmethod
    def from_web3(cls, w3: "Web3", addr: ChecksumAddress = None) -> "ENS":
        """
        Generate an ENS instance from a Web3 instance

        :param `web3.Web3` w3: to infer connection, middleware, and codec information
        :param hex-string addr: the address of the ENS registry on-chain. If not
            provided, defaults to the mainnet ENS registry address.
        """
        provider = w3.manager.provider
        middleware = w3.middleware_onion.middleware
        ns = cls(cast("BaseProvider", provider), addr=addr, middleware=middleware)

        # inherit strict bytes checking from w3 instance
        ns.strict_bytes_type_checking = w3.strict_bytes_type_checking

        return ns

    def address(
        self,
        name: str,
        coin_type: Optional[int] = None,
    ) -> Optional[ChecksumAddress]:
        """
        Look up the Ethereum address that `name` currently points to.

        :param str name: an ENS name to look up
        :param int coin_type: if provided, look up the address for this coin type
        :raises InvalidName: if `name` has invalid syntax
        :raises ResolverNotFound: if no resolver found for `name`
        :raises UnsupportedFunction: if the resolver does not support the ``addr()``
                function
        """
        if coin_type is None:
            # don't validate `addr(bytes32)` interface id since extended resolvers
            # can implement a "resolve" function as of ENSIP-10
            return cast(ChecksumAddress, self._resolve(name, "addr"))
        else:
            r = self.resolver(name)
            _validate_resolver_and_interface_id(
                name, r, ENS_MULTICHAIN_ADDRESS_INTERFACE_ID, "addr(bytes32,uint256)"
            )
            node = raw_name_to_hash(name)
            address_as_bytes = r.caller.addr(node, coin_type)
            if is_none_or_zero_address(address_as_bytes):
                return None
            return to_checksum_address(address_as_bytes)

    def setup_address(
        self,
        name: str,
        address: Union[Address, ChecksumAddress, HexAddress] = cast(  # noqa: B008
            ChecksumAddress, default
        ),
        coin_type: Optional[int] = None,
        transact: Optional["TxParams"] = None,
    ) -> Optional[HexBytes]:
        """
        Set up the name to point to the supplied address.
        The sender of the transaction must own the name, or
        its parent name.

        Example: If the caller owns ``parentname.eth`` with no subdomains
        and calls this method with ``sub.parentname.eth``,
        then ``sub`` will be created as part of this call.

        :param str name: ENS name to set up
        :param str address: name will point to this address, in checksum format.
            If ``None``, erase the record. If not specified, name will point
            to the owner's address.
        :param int coin_type: if provided, set up the address for this coin type
        :param dict transact: the transaction configuration, like in
            :meth:`~web3.eth.Eth.send_transaction`
        :raises InvalidName: if ``name`` has invalid syntax
        :raises UnauthorizedError: if ``'from'`` in `transact` does not own `name`
        """
        if not transact:
            transact = {}

        transact = deepcopy(transact)
        owner = self.setup_owner(name, transact=transact)
        self._assert_control(owner, name)
        if is_none_or_zero_address(address):
            address = None
        elif address is default:
            address = owner
        elif is_binary_address(address):
            address = to_checksum_address(cast(str, address))
        elif not is_checksum_address(address):
            raise ENSValueError("You must supply the address in checksum format")
        if self.address(name) == address:
            return None
        if address is None:
            address = EMPTY_ADDR_HEX
        transact["from"] = owner

        resolver: "Contract" = self._set_resolver(name, transact=transact)
        node = raw_name_to_hash(name)

        if coin_type is None:
            return resolver.functions.setAddr(node, address).transact(transact)
        else:
            return resolver.functions.setAddr(node, coin_type, address).transact(
                transact
            )

    def name(self, address: ChecksumAddress) -> Optional[str]:
        """
        Look up the name that the address points to, using a
        reverse lookup. Reverse lookup is opt-in for name owners.

        :param address:
        :type address: hex-string
        """
        reversed_domain = address_to_reverse_domain(address)
        name = self._resolve(reversed_domain, fn_name="name")

        # To be absolutely certain of the name, via reverse resolution,
        # the address must match in the forward resolution
        return name if to_checksum_address(address) == self.address(name) else None

    def setup_name(
        self,
        name: str,
        address: Optional[ChecksumAddress] = None,
        transact: Optional["TxParams"] = None,
    ) -> HexBytes:
        """
        Set up the address for reverse lookup, aka "caller ID".
        After successful setup, the method :meth:`~ens.ENS.name` will return
        `name` when supplied with `address`.

        :param str name: ENS name that address will point to
        :param str address: address to set up, in checksum format
        :param dict transact: the transaction configuration, like in
            :meth:`~web3.eth.send_transaction`
        :raises AddressMismatch: if the name does not already point to the address
        :raises InvalidName: if `name` has invalid syntax
        :raises UnauthorizedError: if ``'from'`` in `transact` does not own `name`
        :raises UnownedName: if no one owns `name`
        """
        if not transact:
            transact = {}
        transact = deepcopy(transact)
        if not name:
            self._assert_control(address, "the reverse record")
            return self._setup_reverse(None, address, transact=transact)
        else:
            resolved = self.address(name)
            if is_none_or_zero_address(address):
                address = resolved
            elif resolved and address != resolved and resolved != EMPTY_ADDR_HEX:
                raise AddressMismatch(
                    f"Could not set address {address!r} to point to name, "
                    f"because the name resolves to {resolved!r}. "
                    "To change the name for an existing address, call "
                    "setup_address() first."
                )
            if is_none_or_zero_address(address):
                address = self.owner(name)
            if is_none_or_zero_address(address):
                raise UnownedName("claim subdomain using setup_address() first")
            if is_binary_address(address):
                address = to_checksum_address(address)
            if not is_checksum_address(address):
                raise ENSValueError("You must supply the address in checksum format")
            self._assert_control(address, name)
            if not resolved:
                self.setup_address(name, address, transact=transact)
            return self._setup_reverse(name, address, transact=transact)

    def owner(self, name: str) -> ChecksumAddress:
        """
        Get the owner of a name. Note that this may be different from the
        deed holder in the '.eth' registrar. Learn more about the difference
        between deed and name ownership in the ENS `Managing Ownership docs
        <http://docs.ens.domains/en/latest/userguide.html#managing-ownership>`_

        :param str name: ENS name to look up
        :return: owner address
        :rtype: str
        """
        node = raw_name_to_hash(name)
        return self.ens.caller.owner(node)

    def setup_owner(
        self,
        name: str,
        new_owner: ChecksumAddress = None,
        transact: Optional["TxParams"] = None,
    ) -> Optional[ChecksumAddress]:
        """
        Set the owner of the supplied name to `new_owner`.

        For typical scenarios, you'll never need to call this method directly,
        simply call :meth:`setup_name` or :meth:`setup_address`. This method does *not*
        set up the name to point to an address.

        If `new_owner` is not supplied, then this will assume you
        want the same owner as the parent domain.

        If the caller owns ``parentname.eth`` with no subdomains
        and calls this method with ``sub.parentname.eth``,
        then ``sub`` will be created as part of this call.

        :param str name: ENS name to set up
        :param new_owner: account that will own `name`. If ``None``, set owner to
            empty addr. If not specified, name will point to the parent domain
            owner's address.
        :param dict transact: the transaction configuration, like in
            :meth:`~web3.eth.Eth.send_transaction`
        :raises InvalidName: if `name` has invalid syntax
        :raises UnauthorizedError: if ``'from'`` in `transact` does not own `name`
        :returns: the new owner's address
        """
        new_owner = new_owner or cast(ChecksumAddress, default)
        if not transact:
            transact = {}

        transact = deepcopy(transact)
        (super_owner, unowned, owned) = self._first_owner(name)
        if new_owner is default:
            new_owner = super_owner
        elif not new_owner:
            new_owner = ChecksumAddress(EMPTY_ADDR_HEX)
        else:
            new_owner = to_checksum_address(new_owner)
        current_owner = self.owner(name)
        if new_owner == EMPTY_ADDR_HEX and not current_owner:
            return None
        elif current_owner == new_owner:
            return current_owner
        else:
            self._assert_control(super_owner, name, owned)
            self._claim_ownership(
                new_owner, unowned, owned, super_owner, transact=transact
            )
            return new_owner

    def resolver(self, name: str) -> Optional["Contract"]:
        """
        Get the resolver for an ENS name.

        :param str name: The ENS name
        """
        normal_name = normalize_name(name)
        return self._get_resolver(normal_name)[0]

    def reverser(self, target_address: ChecksumAddress) -> Optional["Contract"]:
        reversed_domain = address_to_reverse_domain(target_address)
        return self.resolver(reversed_domain)

    # -- text records -- #

    def get_text(self, name: str, key: str) -> str:
        """
        Get the value of a text record by key from an ENS name.

        :param str name: ENS name to look up
        :param str key: ENS name's text record key
        :return: ENS name's text record value
        :rtype: str
        :raises UnsupportedFunction: If the resolver does not support
            the "0x59d1d43c" interface id
        :raises ResolverNotFound: If no resolver is found for the provided name
        """
        node = raw_name_to_hash(name)

        r = self.resolver(name)
        _validate_resolver_and_interface_id(name, r, ENS_TEXT_INTERFACE_ID, "text")
        return r.caller.text(node, key)

    def set_text(
        self,
        name: str,
        key: str,
        value: str,
        transact: "TxParams" = None,
    ) -> HexBytes:
        """
        Set the value of a text record of an ENS name.

        :param str name: ENS name
        :param str key: Name of the attribute to set
        :param str value: Value to set the attribute to
        :param dict transact: The transaction configuration, like in
            :meth:`~web3.eth.Eth.send_transaction`
        :return: Transaction hash
        :rtype: HexBytes
        :raises UnsupportedFunction: If the resolver does not support
            the "0x59d1d43c" interface id
        :raises ResolverNotFound: If no resolver is found for the provided name
        """
        r = self.resolver(name)
        _validate_resolver_and_interface_id(name, r, ENS_TEXT_INTERFACE_ID, "text")
        node = raw_name_to_hash(name)

        return self._set_property(
            name, r.functions.setText, (node, key, value), transact
        )

    # -- private methods -- #

    def _get_resolver(
        self,
        normal_name: str,
        fn_name: str = "addr",
    ) -> Tuple[Optional["Contract"], str]:
        current_name = normal_name

        # look for a resolver, starting at the full name and taking the parent
        # each time that no resolver is found
        while True:
            if is_empty_name(current_name):
                # if no resolver found across all iterations, current_name
                # will eventually be the empty string '' which returns here
                return None, current_name

            resolver_addr = self.ens.caller.resolver(normal_name_to_hash(current_name))
            if not is_none_or_zero_address(resolver_addr):
                # if resolver found, return it
                resolver = cast(
                    "Contract", self._type_aware_resolver(resolver_addr, fn_name)
                )
                return resolver, current_name

            # set current_name to parent and try again
            current_name = self.parent(current_name)

    def _set_resolver(
        self,
        name: str,
        resolver_addr: Optional[ChecksumAddress] = None,
        transact: Optional["TxParams"] = None,
    ) -> "Contract":
        if not transact:
            transact = {}
        transact = deepcopy(transact)
        if is_none_or_zero_address(resolver_addr):
            resolver_addr = self.address("resolver.eth")
        namehash = raw_name_to_hash(name)
        if self.ens.caller.resolver(namehash) != resolver_addr:
            self.ens.functions.setResolver(namehash, resolver_addr).transact(transact)
        return cast("Contract", self._resolver_contract(address=resolver_addr))

    def _resolve(
        self, name: str, fn_name: str = "addr"
    ) -> Optional[Union[ChecksumAddress, str]]:
        normal_name = normalize_name(name)
        resolver, current_name = self._get_resolver(normal_name, fn_name)
        if not resolver:
            return None

        node = self.namehash(normal_name)

        # handle extended resolver case
        if _resolver_supports_interface(resolver, ENS_EXTENDED_RESOLVER_INTERFACE_ID):
            contract_func_with_args = (fn_name, [node])

            calldata = resolver.encode_abi(*contract_func_with_args)
            contract_call_result = resolver.caller.resolve(
                ens_encode_name(normal_name),
                calldata,
            )
            result = self._decode_ensip10_resolve_data(
                contract_call_result, resolver, fn_name
            )
            return to_checksum_address(result) if is_address(result) else result
        elif normal_name == current_name:
            lookup_function = getattr(resolver.functions, fn_name)
            result = lookup_function(node).call()
            if is_none_or_zero_address(result):
                return None
            return to_checksum_address(result) if is_address(result) else result
        return None

    def _assert_control(
        self,
        account: ChecksumAddress,
        name: str,
        parent_owned: Optional[str] = None,
    ) -> None:
        if not address_in(account, self.w3.eth.accounts):
            raise UnauthorizedError(
                f"in order to modify {name!r}, you must control account"
                f" {account!r}, which owns {parent_owned or name!r}"
            )

    def _first_owner(
        self, name: str
    ) -> Tuple[Optional[ChecksumAddress], Sequence[str], str]:
        """
        Takes a name, and returns the owner of the deepest subdomain that has an owner

        :returns: (owner or None, list(unowned_subdomain_labels), first_owned_domain)
        """
        owner = None
        unowned = []
        pieces = normalize_name(name).split(".")
        while pieces and is_none_or_zero_address(owner):
            name = ".".join(pieces)
            owner = self.owner(name)
            if is_none_or_zero_address(owner):
                unowned.append(pieces.pop(0))
        return (owner, unowned, name)

    def _claim_ownership(
        self,
        owner: ChecksumAddress,
        unowned: Sequence[str],
        owned: str,
        old_owner: Optional[ChecksumAddress] = None,
        transact: Optional["TxParams"] = None,
    ) -> None:
        if not transact:
            transact = {}
        transact = deepcopy(transact)
        transact["from"] = old_owner or owner
        for label in reversed(unowned):
            self.ens.functions.setSubnodeOwner(
                raw_name_to_hash(owned),
                label_to_hash(label),
                owner,
            ).transact(transact)
            owned = f"{label}.{owned}"

    def _setup_reverse(
        self,
        name: Optional[str],
        address: ChecksumAddress,
        transact: Optional["TxParams"] = None,
    ) -> HexBytes:
        name = normalize_name(name) if name else ""
        if not transact:
            transact = {}
        transact = deepcopy(transact)
        transact["from"] = address
        return self._reverse_registrar().functions.setName(name).transact(transact)

    def _reverse_registrar(self) -> "Contract":
        addr = self.ens.caller.owner(normal_name_to_hash(REVERSE_REGISTRAR_DOMAIN))
        return self.w3.eth.contract(address=addr, abi=abis.REVERSE_REGISTRAR)

    def _set_property(
        self,
        name: str,
        func: "ContractFunction",
        args: Sequence[Any],
        transact: "TxParams" = None,
    ) -> HexBytes:
        if not transact:
            transact = {}

        owner = self.owner(name)
        transact_from_owner = merge({"from": owner}, transact)

        return func(*args).transact(transact_from_owner)


def _validate_resolver_and_interface_id(
    ens_name: str,
    resolver: "Contract",
    ens_interface_id: HexStr,
    interface_name: str,
) -> None:
    if not resolver:
        raise ResolverNotFound(
            f"No resolver found for name `{ens_name}`. It is likely the name "
            "contains an unsupported top level domain (tld)."
        )
    elif not _resolver_supports_interface(resolver, ens_interface_id):
        raise UnsupportedFunction(
            f"Resolver for name `{ens_name}` does not support the `{interface_name}` "
            f"interface."
        )


def _resolver_supports_interface(
    resolver: "Contract",
    ens_interface_id: HexStr,
) -> bool:
    return any(
        "supportsInterface" in repr(func) for func in resolver.all_functions()
    ) and resolver.caller.supportsInterface(ens_interface_id)
