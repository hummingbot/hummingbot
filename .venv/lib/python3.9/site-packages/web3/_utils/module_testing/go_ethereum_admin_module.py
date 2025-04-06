import pytest
from typing import (
    TYPE_CHECKING,
    List,
)

from web3.datastructures import (
    AttributeDict,
)
from web3.types import (
    EnodeURI,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


class GoEthereumAdminModuleTest:
    def test_add_peer(self, w3: "Web3") -> None:
        result = w3.geth.admin.add_peer(
            EnodeURI(
                "enode://f1a6b0bdbf014355587c3018454d070ac57801f05d3b39fe85da574f002a32e929f683d72aa5a8318382e4d3c7a05c9b91687b0d997a39619fb8a6e7ad88e512@1.1.1.1:30303"  # noqa: E501
            ),
        )
        assert result is True

    def test_admin_datadir(self, w3: "Web3", datadir: str) -> None:
        result = w3.geth.admin.datadir()
        assert result == datadir

    def test_admin_node_info(self, w3: "Web3") -> None:
        result = w3.geth.admin.node_info()
        expected = AttributeDict(
            {
                "id": "",
                "name": "",
                "enode": "",
                "ip": "",
                "ports": AttributeDict({}),
                "listenAddr": "",
                "protocols": AttributeDict({}),
            }
        )
        # Test that result gives at least the keys that are listed in `expected`
        assert not set(expected.keys()).difference(result.keys())

    def test_admin_peers(self, w3: "Web3") -> None:
        enode = w3.geth.admin.node_info()["enode"]
        w3.geth.admin.add_peer(enode)
        result = w3.geth.admin.peers()
        assert len(result) == 1

    def test_admin_start_stop_http(self, w3: "Web3") -> None:
        stop = w3.geth.admin.stop_http()
        assert stop is True

        start = w3.geth.admin.start_http()
        assert start is True

    def test_admin_start_stop_ws(self, w3: "Web3") -> None:
        stop = w3.geth.admin.stop_ws()
        assert stop is True

        start = w3.geth.admin.start_ws()
        assert start is True


class GoEthereumAsyncAdminModuleTest:
    @pytest.mark.asyncio
    async def test_async_datadir(self, async_w3: "AsyncWeb3") -> None:
        datadir = await async_w3.geth.admin.datadir()
        assert isinstance(datadir, str)

    @pytest.mark.asyncio
    async def test_async_node_info(self, async_w3: "AsyncWeb3") -> None:
        node_info = await async_w3.geth.admin.node_info()
        assert "Geth" in node_info["name"]

    @pytest.mark.asyncio
    async def test_async_nodes(self, async_w3: "AsyncWeb3") -> None:
        nodes = await async_w3.geth.admin.peers()
        assert isinstance(nodes, List)

    @pytest.mark.asyncio
    async def test_admin_peers(self, async_w3: "AsyncWeb3") -> None:
        node_info = await async_w3.geth.admin.node_info()
        await async_w3.geth.admin.add_peer(node_info["enode"])
        result = await async_w3.geth.admin.peers()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_admin_start_stop_http(self, async_w3: "AsyncWeb3") -> None:
        stop = await async_w3.geth.admin.stop_http()
        assert stop is True

        start = await async_w3.geth.admin.start_http()
        assert start is True

    @pytest.mark.asyncio
    async def test_admin_start_stop_ws(self, async_w3: "AsyncWeb3") -> None:
        stop = await async_w3.geth.admin.stop_ws()
        assert stop is True

        start = await async_w3.geth.admin.start_ws()
        assert start is True
