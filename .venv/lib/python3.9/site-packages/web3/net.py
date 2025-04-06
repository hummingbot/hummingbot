from typing import (
    Awaitable,
    Callable,
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


class Net(Module):
    _listening: Method[Callable[[], bool]] = Method(
        RPC.net_listening,
        mungers=[default_root_munger],
    )

    _peer_count: Method[Callable[[], int]] = Method(
        RPC.net_peerCount,
        mungers=[default_root_munger],
    )

    _version: Method[Callable[[], str]] = Method(
        RPC.net_version,
        mungers=[default_root_munger],
    )

    @property
    def listening(self) -> bool:
        return self._listening()

    @property
    def peer_count(self) -> int:
        return self._peer_count()

    @property
    def version(self) -> str:
        return self._version()


class AsyncNet(Module):
    is_async = True

    _listening: Method[Callable[[], Awaitable[bool]]] = Method(
        RPC.net_listening,
        mungers=[default_root_munger],
    )

    _peer_count: Method[Callable[[], Awaitable[int]]] = Method(
        RPC.net_peerCount,
        mungers=[default_root_munger],
    )

    _version: Method[Callable[[], Awaitable[str]]] = Method(
        RPC.net_version,
        mungers=[default_root_munger],
    )

    @property
    async def listening(self) -> bool:
        return await self._listening()

    @property
    async def peer_count(self) -> int:
        return await self._peer_count()

    @property
    async def version(self) -> str:
        return await self._version()
