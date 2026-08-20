"""Every Gateway field name this package uses must exist in Gateway's OpenAPI spec.

test_gateway_paths_exist pins the routes; this pins what travels over them. These
modules hand-write camelCase keys into query strings and JSON bodies, and read them back
out of responses with ``.get()`` — so a field renamed in Gateway does not raise here. It
reads ``None``, and a strategy acts on a price or balance change of zero. That is not
hypothetical: ``gateway_base.approve_token`` read ``gasPrice`` from a response whose
schema is ``{signature, status, data}``, recording a gas price of 0 on every approval.

The spec is the same vendored copy the path check uses; refresh it the same way:

    cd ../gateway && pnpm generate:openapi
    cp ../gateway/openapi.json gateway-openapi.json

A failure means either the client is stale and should follow the rename, or the key
addresses Gateway's config tree rather than an HTTP field — see CONFIG_TREE_KEYS.

The /trading methods no longer spell their keys as literals — they build the request from
the models generated off the spec, so the names are kwargs. Pydantic catches a misspelled
*required* field, since the real one then goes missing, but silently drops a misspelled
optional one. The last check below covers that case by reading the kwargs out of the
source and holding them against the model each call names.
"""
import json
import os
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = Path(os.environ.get("GATEWAY_OPENAPI", _REPO_ROOT / "gateway-openapi.json"))

# Every module that speaks Gateway's wire format: the client that builds the requests,
# and the connector layer that reads the responses back apart.
CLIENT_PATHS = [
    _REPO_ROOT / "hummingbot" / "core" / "gateway" / "gateway_http_client.py",
    _REPO_ROOT / "hummingbot" / "connector" / "gateway" / "gateway.py",
    _REPO_ROOT / "hummingbot" / "connector" / "gateway" / "gateway_base.py",
]

# camelCase string literals, single- or double-quoted.
_CAMEL_CASE = re.compile(r'["\']([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)["\']')

# Keys that address Gateway's YAML config tree, not an HTTP field: /config returns the
# config as-is, so these arrive as namespaced names ("solana.defaultWallet") that no
# route schema declares. Listed individually so a renamed wire field cannot hide here.
CONFIG_TREE_KEYS = {"defaultNetwork", "defaultWallet", "nativeCurrencySymbol"}

# camelCase strings that are this package's own values rather than Gateway field names.
# The regex cannot tell a dict key from any other string literal, so they are named here.
LOCAL_CONSTANTS = {
    "txDataUnavailable",  # gateway_base.TX_DATA_UNAVAILABLE, a sentinel this side invents
}


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
        cls.used = {
            path: set(_CAMEL_CASE.findall(path.read_text())) for path in CLIENT_PATHS
        }

    def test_spec_actually_loaded(self):
        """Guard the guard: an empty spec would pass the real check vacuously."""
        self.assertGreater(len(self.spec_names), 100, f"Spec at {SPEC_PATH} looks truncated")

    def test_client_keys_were_found(self):
        """Guard the guard: a regex matching nothing would also pass vacuously."""
        for path, keys in self.used.items():
            self.assertGreater(len(keys), 3, f"Only {len(keys)} camelCase keys found in {path.name}")

    def test_every_wire_key_exists_in_the_spec(self):
        unknown = sorted(
            f"{key}  ({path.name})"
            for path, keys in self.used.items()
            for key in keys - self.spec_names - CONFIG_TREE_KEYS - LOCAL_CONSTANTS
        )
        self.assertFalse(
            unknown,
            "This package sends or reads keys Gateway's spec does not declare:\n  "
            + "\n  ".join(unknown)
            + f"\n\nSpec: {SPEC_PATH}. Either the caller is stale and should follow the rename, "
            "or the string is not a Gateway field at all — see CONFIG_TREE_KEYS and "
            "LOCAL_CONSTANTS.",
        )


class GatewayModelKwargsExistTest(unittest.TestCase):
    """Every kwarg passed to a generated request model must be one of its fields.

    Pydantic ignores an unknown keyword. On a required field that still fails loudly —
    the real one is missing — but `slippagePc=1` for `slippagePct` would be dropped in
    silence, and the request would go out without the slippage the caller asked for.
    """

    # `ModelNameRequest(\n    key=..., ...)` — the shape every converted call site uses.
    CONSTRUCTOR = re.compile(r"\b([A-Z][A-Za-z0-9]*Request)\(\s*\n((?:\s+\w+=.*\n)+)")
    KWARG = re.compile(r"^\s+(\w+)=", re.M)

    @classmethod
    def setUpClass(cls):
        from hummingbot.core.gateway import gateway_models

        cls.models = gateway_models
        source = (_REPO_ROOT / "hummingbot" / "core" / "gateway" / "gateway_http_client.py").read_text()
        cls.calls = [
            (match.group(1), cls.KWARG.findall(match.group(2)))
            for match in cls.CONSTRUCTOR.finditer(source)
        ]

    def test_the_call_sites_were_found(self):
        """Guard the guard: a regex matching nothing would pass the real check vacuously."""
        self.assertGreater(len(self.calls), 10, f"Only {len(self.calls)} model constructions found")

    def test_every_kwarg_is_a_field_of_the_model_it_names(self):
        unknown = []
        for model_name, kwargs in self.calls:
            model = getattr(self.models, model_name, None)
            self.assertIsNotNone(model, f"{model_name} is not a generated model")
            fields = {(f.alias or n) for n, f in model.model_fields.items()}
            fields |= set(model.model_fields)
            unknown += [f"{model_name}.{k}" for k in kwargs if k not in fields]

        self.assertFalse(
            unknown,
            "GatewayHttpClient passes keywords no generated model declares:\n  "
            + "\n  ".join(sorted(unknown))
            + "\n\nPydantic drops an unknown keyword, so an optional one goes missing in "
            "silence. Follow the rename, or correct the spelling.",
        )


if __name__ == "__main__":
    unittest.main()
