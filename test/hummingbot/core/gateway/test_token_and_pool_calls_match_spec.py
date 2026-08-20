"""Every token and pool call has to send what Gateway's route declares.

The route unification replaced `chain` + `network` with a single `chainNetwork`, and this
family was never migrated. It broke far more than token listing: `GatewayBase` calls
`get_tokens` on the startup path — `load_token_data` fills the amount quantums, so a
connector cannot size an order without it — so every Gateway executor failed to create
with `querystring must have required property 'chainNetwork'`, and nothing about that
message pointed here.

The check is driven by the vendored spec rather than by a list of names, so a future
rename fails here instead of at runtime inside an executor.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

SPEC = json.loads((Path(__file__).parents[4] / "gateway-openapi.json").read_text())


class _Recorder(GatewayHttpClient):
    """A client whose requests are captured instead of sent."""

    def __init__(self):
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []

    async def api_request(self, method, path_url, params={}, fail_silently=False, use_body=False, **kwargs):
        self.calls.append((method, path_url, dict(params)))
        return {}


def _spec_params(route: str, method: str) -> Tuple[set, set]:
    """(declared, required) parameter names for a route, query params and body alike."""
    operation = SPEC["paths"][route][method]
    declared = {p["name"] for p in operation.get("parameters", []) if p["in"] == "query"}
    required = {p["name"] for p in operation.get("parameters", []) if p["in"] == "query" and p.get("required")}

    body = operation.get("requestBody")
    if body:
        schema = body["content"]["application/json"]["schema"]
        if "$ref" in schema:
            schema = SPEC["components"]["schemas"][schema["$ref"].split("/")[-1]]
        declared |= set(schema.get("properties", {}))
        required |= set(schema.get("required", []))
    return declared, required


async def _call(name, **kwargs):
    client = _Recorder()
    await getattr(client, name)(**kwargs)
    return client.calls[0]


CHAIN = {"chain": "solana", "network": "mainnet-beta"}

# (client method, kwargs, spec route, spec method). The path the client builds is not
# always the spec's templated one, so the pairing is written out rather than guessed.
CASES = [
    ("get_tokens", CHAIN, "/tokens/", "get"),
    ("get_token", {"symbol_or_address": "SOL", **CHAIN}, "/tokens/{symbolOrAddress}", "get"),
    ("add_token", {**CHAIN, "token_data": {"symbol": "X"}}, "/tokens/", "post"),
    ("get_pool", {"trading_pair": "SOL-USDC", **CHAIN}, "/pools/{tradingPair}", "get"),
    (
        "add_pool",
        {
            **CHAIN,
            "connector": "raydium",
            # The route requires the token addresses and the caller supplies them inside
            # pool_data, which add_pool spreads into the body.
            "pool_data": {
                "address": "pool",
                "type": "amm",
                "baseTokenAddress": "base",
                "quoteTokenAddress": "quote",
            },
        },
        "/pools/",
        "post",
    ),
    ("list_pools", CHAIN, "/pools/", "get"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,kwargs,route,method", CASES)
async def test_the_call_sends_every_required_parameter(name, kwargs, route, method):
    _, _, params = await _call(name, **kwargs)
    _, required = _spec_params(route, method)

    assert required <= set(params), f"{name} omits {required - set(params)}"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,kwargs,route,method", CASES)
async def test_the_call_sends_nothing_the_route_does_not_declare(name, kwargs, route, method):
    _, _, params = await _call(name, **kwargs)
    declared, _ = _spec_params(route, method)

    # add_pool spreads the caller's pool_data in, which is the route's own body shape.
    unknown = set(params) - declared - {"symbol", "token"}
    assert not unknown, f"{name} sends {unknown}, which /{route} does not declare"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("remove_token", {"address": "x", **CHAIN}),
        ("remove_pool", {"address": "x", **CHAIN}),
    ],
)
async def test_a_delete_carries_the_selector_on_the_url(name, kwargs):
    # api_request sends DELETE params as a JSON body, and Gateway declares these as
    # querystring, so they have to ride the path.
    _, path, _ = await _call(name, **kwargs)

    assert "chainNetwork=solana-mainnet-beta" in path
    assert "chain=solana" not in path


@pytest.mark.asyncio
async def test_the_wallet_routes_still_speak_chain_alone():
    # Not swept into the rename: wallets are stored per chain on disk, because a keypair
    # works on every network of that chain. Gateway's RemoveWalletRequest still declares
    # `chain`, and this pins the asymmetry as deliberate.
    declared, _ = _spec_params("/wallet/remove", "delete")

    assert "chain" in declared
    assert "chainNetwork" not in declared
