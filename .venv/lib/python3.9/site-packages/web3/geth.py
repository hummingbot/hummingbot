from typing import (
    Awaitable,
    Callable,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
)

from eth_typing.evm import (
    ChecksumAddress,
)

from web3._utils.rpc_abi import (
    RPC,
)
from web3.method import (
    Method,
    default_root_munger,
)
from web3.module import (
    Module,
)
from web3.types import (
    CallTrace,
    DiffModeTrace,
    EnodeURI,
    FourByteTrace,
    NodeInfo,
    OpcodeTrace,
    Peer,
    PrestateTrace,
    TraceConfig,
    TxPoolContent,
    TxPoolInspect,
    TxPoolStatus,
    _Hash32,
)


class UnlockAccountWrapper(Protocol):
    def __call__(
        self,
        account: ChecksumAddress,
        passphrase: str,
        duration: Optional[int] = None,
    ) -> bool:
        pass


class GethTxPool(Module):
    """
    https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-txpool
    """

    is_async = False

    content: Method[Callable[[], TxPoolContent]] = Method(
        RPC.txpool_content,
        is_property=True,
    )

    inspect: Method[Callable[[], TxPoolInspect]] = Method(
        RPC.txpool_inspect,
        is_property=True,
    )

    status: Method[Callable[[], TxPoolStatus]] = Method(
        RPC.txpool_status,
        is_property=True,
    )


class ServerConnection(Protocol):
    def __call__(
        self,
        host: str = "localhost",
        port: int = 8546,
        cors: str = "",
        apis: str = "eth,net,web3",
    ) -> bool:
        pass


def admin_start_params_munger(
    _module: Module,
    host: str = "localhost",
    port: int = 8546,
    cors: str = "",
    apis: str = "eth,net,web3",
) -> Tuple[str, int, str, str]:
    return (host, port, cors, apis)


class GethAdmin(Module):
    """
    https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-admin
    """

    is_async = False

    add_peer: Method[Callable[[EnodeURI], bool]] = Method(
        RPC.admin_addPeer,
        mungers=[default_root_munger],
    )

    datadir: Method[Callable[[], str]] = Method(
        RPC.admin_datadir,
        is_property=True,
    )

    node_info: Method[Callable[[], NodeInfo]] = Method(
        RPC.admin_nodeInfo,
        is_property=True,
    )

    peers: Method[Callable[[], List[Peer]]] = Method(
        RPC.admin_peers,
        is_property=True,
    )

    start_http: Method[ServerConnection] = Method(
        RPC.admin_startHTTP,
        mungers=[admin_start_params_munger],
    )

    start_ws: Method[ServerConnection] = Method(
        RPC.admin_startWS,
        mungers=[admin_start_params_munger],
    )

    stop_http: Method[Callable[[], bool]] = Method(
        RPC.admin_stopHTTP,
        is_property=True,
    )

    stop_ws: Method[Callable[[], bool]] = Method(
        RPC.admin_stopWS,
        is_property=True,
    )


class GethDebug(Module):
    """
    https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-debug
    """

    def trace_transaction_munger(
        self,
        transaction_hash: _Hash32,
        trace_config: Optional[TraceConfig] = None,
    ) -> Tuple[_Hash32, TraceConfig]:
        return (transaction_hash, trace_config)

    trace_transaction: Method[
        Callable[
            ...,
            Union[CallTrace, PrestateTrace, OpcodeTrace, DiffModeTrace, FourByteTrace],
        ]
    ] = Method(
        RPC.debug_traceTransaction,
        mungers=[trace_transaction_munger],
    )


class Geth(Module):
    admin: GethAdmin
    txpool: GethTxPool
    debug: GethDebug


# --- async --- #


class AsyncGethTxPool(Module):
    """
    https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-txpool
    """

    is_async = True

    _content: Method[Callable[[], Awaitable[TxPoolContent]]] = Method(
        RPC.txpool_content,
        is_property=True,
    )

    async def content(self) -> TxPoolContent:
        return await self._content()

    _inspect: Method[Callable[[], Awaitable[TxPoolInspect]]] = Method(
        RPC.txpool_inspect,
        is_property=True,
    )

    async def inspect(self) -> TxPoolInspect:
        return await self._inspect()

    _status: Method[Callable[[], Awaitable[TxPoolStatus]]] = Method(
        RPC.txpool_status,
        is_property=True,
    )

    async def status(self) -> TxPoolStatus:
        return await self._status()


class AsyncGethAdmin(Module):
    """
    https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-admin
    """

    is_async = True

    _add_peer: Method[Callable[[EnodeURI], Awaitable[bool]]] = Method(
        RPC.admin_addPeer,
        mungers=[default_root_munger],
    )

    async def add_peer(self, node_url: EnodeURI) -> bool:
        return await self._add_peer(node_url)

    _datadir: Method[Callable[[], Awaitable[str]]] = Method(
        RPC.admin_datadir,
        is_property=True,
    )

    async def datadir(self) -> str:
        return await self._datadir()

    _node_info: Method[Callable[[], Awaitable[NodeInfo]]] = Method(
        RPC.admin_nodeInfo,
        is_property=True,
    )

    async def node_info(self) -> NodeInfo:
        return await self._node_info()

    _peers: Method[Callable[[], Awaitable[List[Peer]]]] = Method(
        RPC.admin_peers,
        is_property=True,
    )

    async def peers(self) -> List[Peer]:
        return await self._peers()

    # start_http and stop_http

    _start_http: Method[Callable[[str, int, str, str], Awaitable[bool]]] = Method(
        RPC.admin_startHTTP,
        mungers=[admin_start_params_munger],
    )

    _stop_http: Method[Callable[[], Awaitable[bool]]] = Method(
        RPC.admin_stopHTTP,
        is_property=True,
    )

    async def start_http(
        self,
        host: str = "localhost",
        port: int = 8546,
        cors: str = "",
        apis: str = "eth,net,web3",
    ) -> bool:
        return await self._start_http(host, port, cors, apis)

    async def stop_http(self) -> bool:
        return await self._stop_http()

    # start_ws and stop_ws

    _start_ws: Method[Callable[[str, int, str, str], Awaitable[bool]]] = Method(
        RPC.admin_startWS,
        mungers=[admin_start_params_munger],
    )

    _stop_ws: Method[Callable[[], Awaitable[bool]]] = Method(
        RPC.admin_stopWS,
        is_property=True,
    )

    async def start_ws(
        self,
        host: str = "localhost",
        port: int = 8546,
        cors: str = "",
        apis: str = "eth,net,web3",
    ) -> bool:
        return await self._start_ws(host, port, cors, apis)

    async def stop_ws(self) -> bool:
        return await self._stop_ws()


class AsyncGethDebug(Module):
    """
    https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-debug
    """

    is_async = True

    _trace_transaction: Method[
        Callable[
            ...,
            Awaitable[
                Union[
                    CallTrace, PrestateTrace, OpcodeTrace, FourByteTrace, DiffModeTrace
                ]
            ],
        ]
    ] = Method(RPC.debug_traceTransaction)

    async def trace_transaction(
        self,
        transaction_hash: _Hash32,
        trace_config: Optional[TraceConfig] = None,
    ) -> Union[CallTrace, PrestateTrace, OpcodeTrace, FourByteTrace, DiffModeTrace]:
        return await self._trace_transaction(transaction_hash, trace_config)


class AsyncGeth(Module):
    is_async = True

    admin: AsyncGethAdmin
    txpool: AsyncGethTxPool
    debug: AsyncGethDebug
