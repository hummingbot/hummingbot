import pytest
from typing import (
    TYPE_CHECKING,
)

from eth_utils import (
    is_boolean,
    is_integer,
    is_string,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


class NetModuleTest:
    def test_net_version(self, w3: "Web3") -> None:
        version = w3.net.version

        assert is_string(version)
        assert version.isdigit()

    def test_net_listening(self, w3: "Web3") -> None:
        listening = w3.net.listening

        assert is_boolean(listening)

    def test_net_peer_count(self, w3: "Web3") -> None:
        peer_count = w3.net.peer_count

        assert is_integer(peer_count)


class AsyncNetModuleTest:
    @pytest.mark.asyncio
    async def test_net_version(self, async_w3: "AsyncWeb3") -> None:
        version = await async_w3.net.version

        assert is_string(version)
        assert version.isdigit()

    @pytest.mark.asyncio
    async def test_net_listening(self, async_w3: "AsyncWeb3") -> None:
        listening = await async_w3.net.listening

        assert is_boolean(listening)

    @pytest.mark.asyncio
    async def test_net_peer_count(self, async_w3: "AsyncWeb3") -> None:
        peer_count = await async_w3.net.peer_count

        assert is_integer(peer_count)
