"""A DELETE names what it is deleting on the URL, not in a body.

`api_request` sends DELETE parameters as a JSON body, and Gateway declares `chainNetwork`
as a required *querystring* on both remove routes. Passing it as a parameter therefore
leaves the querystring empty and the request 400s on a field the caller did supply, so
`remove_token` and `remove_pool` build the query into the path themselves.

Nothing here reads Gateway's spec: this pins what the client sends, which is the half that
stays true whatever Gateway's document says next.
"""
from typing import Any, Dict, List, Tuple

import pytest

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

CHAIN = {"chain": "solana", "network": "mainnet-beta"}


class _Recorder(GatewayHttpClient):
    """A client whose requests are captured instead of sent."""

    def __init__(self):
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []

    async def api_request(self, method, path_url, params={}, fail_silently=False, use_body=False, **kwargs):
        self.calls.append((method, path_url, dict(params)))
        return {}


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", ["remove_token", "remove_pool"])
async def test_a_delete_carries_the_selector_on_the_url(method_name):
    client = _Recorder()
    await getattr(client, method_name)(address="x", **CHAIN)
    _, path, _ = client.calls[0]

    assert "chainNetwork=solana-mainnet-beta" in path
    # The pre-unification spelling: two parameters where the route now takes one.
    assert "chain=solana" not in path
