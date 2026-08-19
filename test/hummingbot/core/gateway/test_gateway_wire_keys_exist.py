"""Every Gateway field name GatewayHttpClient uses must exist in Gateway's OpenAPI spec.

test_gateway_paths_exist pins the routes; this pins what travels over them. The client
hand-writes camelCase keys into query strings and JSON bodies, and reads them back out
of responses with ``.get()`` — so a field renamed in Gateway does not raise here. It
reads ``None``, and a strategy acts on a price or balance change of zero.

The spec is the same vendored copy the path check uses; refresh it the same way:

    cd ../gateway && pnpm generate:openapi
    cp ../gateway/openapi.json gateway-openapi.json

A failure means either the client is stale and should follow the rename, or the key
addresses Gateway's config tree rather than an HTTP field — see CONFIG_TREE_KEYS.
"""
import json
import os
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = Path(os.environ.get("GATEWAY_OPENAPI", _REPO_ROOT / "gateway-openapi.json"))
CLIENT_PATH = _REPO_ROOT / "hummingbot" / "core" / "gateway" / "gateway_http_client.py"

# camelCase string literals, single- or double-quoted.
_CAMEL_CASE = re.compile(r'["\']([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)["\']')

# Keys that address Gateway's YAML config tree, not an HTTP field: /config returns the
# config as-is, so these arrive as namespaced names ("solana.defaultWallet") that no
# route schema declares. Listed individually so a renamed wire field cannot hide here.
CONFIG_TREE_KEYS = {"defaultNetwork", "defaultWallet", "nativeCurrencySymbol"}


def _spec_field_names(spec: dict) -> set:
    """Every property and query-parameter name anywhere in the spec.

    Query parameters have to be collected alongside schema properties: Gateway's reads
    are GETs, so their fields live under `parameters` and never reach
    `components.schemas`.
    """
    names = set()

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                names.update(value)
            if key == "parameters" and isinstance(value, list):
                names.update(p["name"] for p in value if isinstance(p, dict) and "name" in p)
            walk(value)

    walk(spec)
    return names


class GatewayWireKeysExistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The spec ships with the repo, so a missing one is a broken checkout, not a
        # reason to skip: skipping here is how a rename reaches production unnoticed.
        assert SPEC_PATH.exists(), (
            f"No Gateway OpenAPI spec at {SPEC_PATH}. It is vendored so this check runs in "
            "CI; restore it with `cp ../gateway/openapi.json gateway-openapi.json`."
        )
        cls.spec_names = _spec_field_names(json.loads(SPEC_PATH.read_text()))
        cls.used = set(_CAMEL_CASE.findall(CLIENT_PATH.read_text()))

    def test_spec_actually_loaded(self):
        """Guard the guard: an empty spec would pass the real check vacuously."""
        self.assertGreater(len(self.spec_names), 100, f"Spec at {SPEC_PATH} looks truncated")

    def test_client_keys_were_found(self):
        """Guard the guard: a regex matching nothing would also pass vacuously."""
        self.assertGreater(len(self.used), 20, f"Only {len(self.used)} camelCase keys found in the client")

    def test_every_wire_key_exists_in_the_spec(self):
        unknown = sorted(self.used - self.spec_names - CONFIG_TREE_KEYS)
        self.assertFalse(
            unknown,
            "GatewayHttpClient sends or reads keys Gateway's spec does not declare:\n  "
            + "\n  ".join(unknown)
            + f"\n\nSpec: {SPEC_PATH}. Either the client is stale and should follow the rename, "
            "or the key addresses Gateway's config tree and belongs in CONFIG_TREE_KEYS.",
        )


if __name__ == "__main__":
    unittest.main()
