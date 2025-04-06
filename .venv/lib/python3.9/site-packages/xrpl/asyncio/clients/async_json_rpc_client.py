"""An async client for interacting with the rippled JSON RPC."""

from xrpl.asyncio.clients.async_client import AsyncClient
from xrpl.asyncio.clients.json_rpc_base import JsonRpcBase


class AsyncJsonRpcClient(AsyncClient, JsonRpcBase):
    """An async client for interacting with the rippled JSON RPC."""

    pass
