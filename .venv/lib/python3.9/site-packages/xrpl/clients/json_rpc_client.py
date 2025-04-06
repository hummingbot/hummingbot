"""A sync client for interacting with the rippled JSON RPC."""

from xrpl.asyncio.clients.json_rpc_base import JsonRpcBase
from xrpl.clients.sync_client import SyncClient


class JsonRpcClient(SyncClient, JsonRpcBase):
    """A sync client for interacting with the rippled JSON RPC."""

    pass
