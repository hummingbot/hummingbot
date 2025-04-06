import decimal
from types import (
    TracebackType,
)

from ens import (
    AsyncENS,
    ENS,
)
from eth_abi.codec import (
    ABICodec,
)
from eth_utils import (
    add_0x_prefix,
    apply_to_return_value,
    from_wei,
    is_address,
    is_checksum_address,
    keccak as eth_utils_keccak,
    remove_0x_prefix,
    to_bytes,
    to_checksum_address,
    to_int,
    to_text,
    to_wei,
)
from functools import (
    wraps,
)
from hexbytes import (
    HexBytes,
)
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

from eth_typing import (
    AnyAddress,
    ChecksumAddress,
    HexStr,
    Primitives,
)
from eth_typing.abi import TypeStr
from eth_utils import (
    combomethod,
)

from web3._utils.abi import (
    build_non_strict_registry,
    build_strict_registry,
    map_abi_data,
)
from web3._utils.compat import (
    Self,
)
from web3._utils.empty import (
    empty,
)
from web3._utils.encoding import (
    hex_encode_abi_type,
    to_hex,
    to_json,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3._utils.module import (
    attach_modules as _attach_modules,
)
from web3._utils.normalizers import (
    abi_ens_resolver,
)
from web3.eth import (
    AsyncEth,
    Eth,
)
from web3.exceptions import (
    Web3TypeError,
    Web3ValidationError,
    Web3ValueError,
)
from web3.geth import (
    AsyncGeth,
    AsyncGethAdmin,
    AsyncGethDebug,
    AsyncGethTxPool,
    Geth,
    GethAdmin,
    GethDebug,
    GethTxPool,
)
from web3.manager import (
    RequestManager as DefaultRequestManager,
)
from web3.middleware.base import MiddlewareOnion
from web3.method import (
    Method,
)
from web3.module import (
    Module,
)
from web3.net import (
    AsyncNet,
    Net,
)
from web3.providers import (
    AsyncBaseProvider,
    BaseProvider,
)
from web3.providers.eth_tester import (
    AsyncEthereumTesterProvider,
    EthereumTesterProvider,
)
from web3.providers.ipc import (
    IPCProvider,
)
from web3.providers.persistent.utils import (
    persistent_connection_provider_method,
)
from web3.providers.rpc import (
    AsyncHTTPProvider,
    HTTPProvider,
)
from web3.providers import (
    LegacyWebSocketProvider,
    WebSocketProvider,
)
from web3.providers.persistent import (
    PersistentConnection,
)
from web3.testing import (
    Testing,
)
from web3.tracing import (
    Tracing,
)
from web3.types import (
    Wei,
)
from web3.providers.persistent.subscription_manager import (
    SubscriptionManager,
)

if TYPE_CHECKING:
    from web3._utils.batching import RequestBatcher  # noqa: F401
    from web3._utils.empty import Empty  # noqa: F401
    from web3.providers.persistent import PersistentConnectionProvider  # noqa: F401


def get_async_default_modules() -> Dict[str, Union[Type[Module], Sequence[Any]]]:
    return {
        "eth": AsyncEth,
        "net": AsyncNet,
        "geth": (
            AsyncGeth,
            {
                "admin": AsyncGethAdmin,
                "txpool": AsyncGethTxPool,
                "debug": AsyncGethDebug,
            },
        ),
    }


def get_default_modules() -> Dict[str, Union[Type[Module], Sequence[Any]]]:
    return {
        "eth": Eth,
        "net": Net,
        "geth": (
            Geth,
            {
                "admin": GethAdmin,
                "txpool": GethTxPool,
                "debug": GethDebug,
            },
        ),
        "tracing": Tracing,
        "testing": Testing,
    }


class BaseWeb3:
    _strict_bytes_type_checking = True

    # Managers
    RequestManager = DefaultRequestManager
    manager: DefaultRequestManager

    # mypy types
    eth: Union[Eth, AsyncEth]
    net: Union[Net, AsyncNet]
    geth: Union[Geth, AsyncGeth]

    @property
    def middleware_onion(self) -> MiddlewareOnion:
        return cast(MiddlewareOnion, self.manager.middleware_onion)

    # Encoding and Decoding
    @staticmethod
    @wraps(to_bytes)
    def to_bytes(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> bytes:
        return to_bytes(primitive, hexstr, text)

    @staticmethod
    @wraps(to_int)
    def to_int(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> int:
        return to_int(primitive, hexstr, text)

    @staticmethod
    @wraps(to_hex)
    def to_hex(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> HexStr:
        return to_hex(primitive, hexstr, text)

    @staticmethod
    @wraps(to_text)
    def to_text(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> str:
        return to_text(primitive, hexstr, text)

    @staticmethod
    @wraps(to_json)
    def to_json(obj: Dict[Any, Any]) -> str:
        return to_json(obj)

    # Currency Utility
    @staticmethod
    @wraps(to_wei)
    def to_wei(number: Union[int, float, str, decimal.Decimal], unit: str) -> Wei:
        return cast(Wei, to_wei(number, unit))

    @staticmethod
    @wraps(from_wei)
    def from_wei(number: int, unit: str) -> Union[int, decimal.Decimal]:
        return from_wei(number, unit)

    # Address Utility
    @staticmethod
    @wraps(is_address)
    def is_address(value: Any) -> bool:
        return is_address(value)

    @staticmethod
    @wraps(is_checksum_address)
    def is_checksum_address(value: Any) -> bool:
        return is_checksum_address(value)

    @staticmethod
    @wraps(to_checksum_address)
    def to_checksum_address(value: Union[AnyAddress, str, bytes]) -> ChecksumAddress:
        return to_checksum_address(value)

    @property
    def api(self) -> str:
        from web3 import __version__

        return __version__

    @property
    def strict_bytes_type_checking(self) -> bool:
        return self._strict_bytes_type_checking

    @strict_bytes_type_checking.setter
    def strict_bytes_type_checking(self, strict_bytes_type_check: bool) -> None:
        self.codec = (
            ABICodec(build_strict_registry())
            if strict_bytes_type_check
            else ABICodec(build_non_strict_registry())
        )
        self._strict_bytes_type_checking = strict_bytes_type_check

    @staticmethod
    @apply_to_return_value(HexBytes)
    def keccak(
        primitive: Optional[Primitives] = None,
        text: Optional[str] = None,
        hexstr: Optional[HexStr] = None,
    ) -> bytes:
        if isinstance(primitive, (bytes, int, type(None))):
            input_bytes = to_bytes(primitive, hexstr=hexstr, text=text)
            return eth_utils_keccak(input_bytes)

        raise Web3TypeError(
            f"You called keccak with first arg {primitive!r} and keywords "
            f"{{'text': {text!r}, 'hexstr': {hexstr!r}}}. You must call it with "
            "one of these approaches: keccak(text='txt'), keccak(hexstr='0x747874'), "
            "keccak(b'\\x74\\x78\\x74'), or keccak(0x747874)."
        )

    @classmethod
    def normalize_values(
        cls, w3: "BaseWeb3", abi_types: List[TypeStr], values: List[Any]
    ) -> List[Any]:
        return map_abi_data([abi_ens_resolver(w3)], abi_types, values)

    @combomethod
    def solidity_keccak(cls, abi_types: List[TypeStr], values: List[Any]) -> bytes:
        """
        Executes keccak256 exactly as Solidity does.
        Takes list of abi_types as inputs -- `[uint24, int8[], bool]`
        and list of corresponding values  -- `[20, [-1, 5, 0], True]`
        """
        if len(abi_types) != len(values):
            raise Web3ValueError(
                "Length mismatch between provided abi types and values.  Got "
                f"{len(abi_types)} types and {len(values)} values."
            )

        if isinstance(cls, type):
            w3 = None
        else:
            w3 = cls
        normalized_values = cls.normalize_values(w3, abi_types, values)

        hex_string = add_0x_prefix(
            HexStr(
                "".join(
                    remove_0x_prefix(hex_encode_abi_type(abi_type, value))
                    for abi_type, value in zip(abi_types, normalized_values)
                )
            )
        )
        return cls.keccak(hexstr=hex_string)

    def attach_modules(
        self, modules: Optional[Dict[str, Union[Type[Module], Sequence[Any]]]]
    ) -> None:
        """
        Attach modules to the `Web3` instance.
        """
        _attach_modules(self, modules)

    def is_encodable(self, _type: TypeStr, value: Any) -> bool:
        return self.codec.is_encodable(_type, value)

    # -- APIs for high-level requests -- #

    def batch_requests(
        self,
    ) -> "RequestBatcher[Method[Callable[..., Any]]]":
        return self.manager._batch_requests()


def _validate_provider(
    w3: Union["Web3", "AsyncWeb3"],
    provider: Optional[Union[BaseProvider, AsyncBaseProvider]],
) -> None:
    if provider is not None:
        if isinstance(w3, AsyncWeb3) and not isinstance(provider, AsyncBaseProvider):
            raise Web3ValidationError(
                "Provider must be an instance of `AsyncBaseProvider` for "
                f"`AsyncWeb3`, got {type(provider)}."
            )

        if isinstance(w3, Web3) and not isinstance(provider, BaseProvider):
            raise Web3ValidationError(
                "Provider must be an instance of `BaseProvider` for `Web3`, "
                f"got {type(provider)}."
            )


class Web3(BaseWeb3):
    # mypy types
    eth: Eth
    net: Net
    geth: Geth

    # Providers
    HTTPProvider = HTTPProvider
    IPCProvider = IPCProvider
    EthereumTesterProvider = EthereumTesterProvider
    LegacyWebSocketProvider = LegacyWebSocketProvider

    def __init__(
        self,
        provider: Optional[BaseProvider] = None,
        middleware: Optional[Sequence[Any]] = None,
        modules: Optional[Dict[str, Union[Type[Module], Sequence[Any]]]] = None,
        external_modules: Optional[
            Dict[str, Union[Type[Module], Sequence[Any]]]
        ] = None,
        ens: Union[ENS, "Empty"] = empty,
    ) -> None:
        _validate_provider(self, provider)

        self.manager = self.RequestManager(self, provider, middleware)
        self.codec = ABICodec(build_strict_registry())

        if modules is None:
            modules = get_default_modules()

        self.attach_modules(modules)

        if external_modules is not None:
            self.attach_modules(external_modules)

        self.ens = ens

    def is_connected(self, show_traceback: bool = False) -> bool:
        return self.provider.is_connected(show_traceback)

    @property
    def provider(self) -> BaseProvider:
        return cast(BaseProvider, self.manager.provider)

    @provider.setter
    def provider(self, provider: BaseProvider) -> None:
        self.manager.provider = provider

    @property
    def client_version(self) -> str:
        return self.manager.request_blocking(RPC.web3_clientVersion, [])

    @property
    def ens(self) -> Union[ENS, "Empty"]:
        if self._ens is empty:
            ns = ENS.from_web3(self)
            ns.w3 = self
            return ns

        return self._ens

    @ens.setter
    def ens(self, new_ens: Union[ENS, "Empty"]) -> None:
        if new_ens:
            new_ens.w3 = self  # set self object reference for ``ENS.w3``
        self._ens = new_ens


# -- async -- #


class AsyncWeb3(BaseWeb3):
    # mypy Types
    eth: AsyncEth
    net: AsyncNet
    geth: AsyncGeth

    # Providers
    AsyncHTTPProvider = AsyncHTTPProvider
    WebSocketProvider = WebSocketProvider
    AsyncEthereumTesterProvider = AsyncEthereumTesterProvider

    def __init__(
        self,
        provider: Optional[AsyncBaseProvider] = None,
        middleware: Optional[Sequence[Any]] = None,
        modules: Optional[Dict[str, Union[Type[Module], Sequence[Any]]]] = None,
        external_modules: Optional[
            Dict[str, Union[Type[Module], Sequence[Any]]]
        ] = None,
        ens: Union[AsyncENS, "Empty"] = empty,
    ) -> None:
        _validate_provider(self, provider)

        self.manager = self.RequestManager(self, provider, middleware)
        self.codec = ABICodec(build_strict_registry())

        self._modules = get_async_default_modules() if modules is None else modules
        self._external_modules = None if external_modules is None else external_modules

        self.attach_modules(self._modules)
        if external_modules is not None:
            self.attach_modules(external_modules)

        self.ens = ens

    async def is_connected(self, show_traceback: bool = False) -> bool:
        return await self.provider.is_connected(show_traceback)

    @property
    def provider(self) -> AsyncBaseProvider:
        return cast(AsyncBaseProvider, self.manager.provider)

    @provider.setter
    def provider(self, provider: AsyncBaseProvider) -> None:
        self.manager.provider = provider

    @property
    async def client_version(self) -> str:
        return await self.manager.coro_request(RPC.web3_clientVersion, [])

    @property
    def ens(self) -> Union[AsyncENS, "Empty"]:
        if self._ens is empty:
            ns = AsyncENS.from_web3(self)
            ns.w3 = self
            return ns
        return self._ens

    @ens.setter
    def ens(self, new_ens: Union[AsyncENS, "Empty"]) -> None:
        if new_ens:
            new_ens.w3 = self  # set self object reference for ``AsyncENS.w3``
        self._ens = new_ens

    # -- persistent connection settings -- #

    _subscription_manager: Optional[SubscriptionManager] = None
    _persistent_connection: Optional["PersistentConnection"] = None

    @property
    @persistent_connection_provider_method()
    def subscription_manager(self) -> SubscriptionManager:
        """
        Access the subscription manager for the current PersistentConnectionProvider.
        """
        if not self._subscription_manager:
            self._subscription_manager = SubscriptionManager(self)
        return self._subscription_manager

    @property
    @persistent_connection_provider_method()
    def socket(self) -> PersistentConnection:
        if self._persistent_connection is None:
            self._persistent_connection = PersistentConnection(self)
        return self._persistent_connection

    # w3 = await AsyncWeb3(PersistentConnectionProvider(...))
    @persistent_connection_provider_method(
        "Provider must inherit from ``PersistentConnectionProvider`` class "
        "when instantiating via ``await``."
    )
    def __await__(self) -> Generator[Any, None, Self]:
        async def __async_init__() -> Self:
            provider = cast("PersistentConnectionProvider", self.provider)
            await provider.connect()
            # set signal handlers since not within a context manager
            provider._set_signal_handlers()
            return self

        return __async_init__().__await__()

    # async with AsyncWeb3(PersistentConnectionProvider(...)) as w3:
    @persistent_connection_provider_method(
        message="Provider must inherit from ``PersistentConnectionProvider`` class "
        "when instantiating via ``async with``."
    )
    async def __aenter__(self) -> Self:
        await self.provider.connect()
        return self

    @persistent_connection_provider_method()
    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        await self.provider.disconnect()

    # async for w3 in AsyncWeb3(PersistentConnectionProvider(...)):
    @persistent_connection_provider_method(
        message="Provider must inherit from ``PersistentConnectionProvider`` class "
        "when instantiating via ``async for``."
    )
    async def __aiter__(self) -> AsyncIterator[Self]:
        provider = self.provider
        while True:
            await provider.connect()
            yield self
            cast("PersistentConnectionProvider", provider).logger.error(
                "Connection interrupted, attempting to reconnect..."
            )
            await provider.disconnect()
