"""Every Gateway path GatewayHttpClient calls must exist in Gateway's OpenAPI spec.

This client is hand-written against an API defined in another repository, so a route
rename there is invisible here until a call 404s at runtime — mid-trade. That has
happened: /trading/swap/* became /trading/{router,clmm,amm}/*-swap, and the per-connector
/connectors/{dex}/{type}/* surface was removed entirely. Both were found by reading
Gateway's source by hand.

This asserts the paths instead, against a vendored copy of Gateway's OpenAPI spec.

The copy is vendored rather than read from a sibling checkout so the check runs in CI,
where no gateway repo exists — and so that adopting a Gateway change is a reviewable diff
of that file, showing exactly which routes moved. Refresh it deliberately:

    cd ../gateway && pnpm generate:openapi
    cp ../gateway/openapi.json gateway-openapi.json

A failure here means one of two things: the client is stale and should follow the spec, or
the spec is stale and should be refreshed. Point GATEWAY_OPENAPI at a live spec to check
against an unmerged Gateway branch without touching the vendored copy.
"""
import json
import os
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = Path(os.environ.get("GATEWAY_OPENAPI", _REPO_ROOT / "gateway-openapi.json"))
CLIENT_PATH = _REPO_ROOT / "hummingbot" / "core" / "gateway" / "gateway_http_client.py"

# Paths passed to api_request(). Both plain and f-strings: the trading routes
# interpolate the type, and the LP verbs go through _lp_route.
_API_REQUEST = re.compile(r'api_request\(\s*\n?\s*"[a-z]+"\s*,\s*\n?\s*f?"([^"]+)"', re.MULTILINE)

# Interpolated segments stand for a runtime choice; expand each to the values it can
# take so the check stays exact instead of pattern-matching.
_SEGMENT_VALUES = {
    "{trading_type}": ["router", "clmm", "amm"],
    "{verb}": [
        "open", "close", "add", "remove", "collect-fees",
        "create-pool", "position-info", "positions-owned", "quote-liquidity",
        "pool-info", "fetch-pools",
    ],
}

# Real Gateway routes that carry no TypeBox schema, so @fastify/swagger omits them from
# the spec. Listed explicitly with where they live, so the exemption is reviewable and a
# genuinely deleted route cannot hide behind it.
_UNSCHEMAD_ROUTES = {
    "/restart",  # src/app.ts — server.post('/restart'), no schema attached
}


def _shape(path: str) -> str:
    """Compare by segment shape: the spec names ids differently ({address} vs {token})."""
    return re.sub(r"\{[^}]+\}", "{}", path.split("?")[0].rstrip("/"))


def _expand(path: str) -> list:
    candidates = [f"/{path.lstrip('/')}"]
    for token, values in _SEGMENT_VALUES.items():
        if any(token in c for c in candidates):
            candidates = [c.replace(token, v) for c in candidates for v in values]
    return candidates


class GatewayPathsExistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The spec ships with the repo, so a missing one is a broken checkout, not a
        # reason to skip: skipping here is how a rename reaches production unnoticed.
        assert SPEC_PATH.exists(), (
            f"No Gateway OpenAPI spec at {SPEC_PATH}. It is vendored so this check runs in "
            "CI; restore it with `cp ../gateway/openapi.json gateway-openapi.json`."
        )
        cls.spec_shapes = {_shape(p) for p in json.loads(SPEC_PATH.read_text()).get("paths", {})}
        cls.called = set(_API_REQUEST.findall(CLIENT_PATH.read_text()))

    def test_spec_actually_loaded(self):
        """Guard the guard: an empty spec would pass the real check vacuously."""
        self.assertGreater(len(self.spec_shapes), 20, f"Spec at {SPEC_PATH} looks truncated")

    def test_client_paths_were_found(self):
        """Guard the guard: a regex matching nothing would also pass vacuously."""
        self.assertGreater(len(self.called), 15, f"Only {len(self.called)} paths found in the client")

    def test_every_called_path_exists_in_the_spec(self):
        missing = [
            candidate
            for called in sorted(self.called)
            for candidate in _expand(called)
            if _shape(candidate) not in self.spec_shapes and candidate not in _UNSCHEMAD_ROUTES
        ]
        self.assertFalse(
            missing,
            "GatewayHttpClient calls paths Gateway does not serve:\n  "
            + "\n  ".join(missing)
            + f"\n\nSpec: {SPEC_PATH} ({len(self.spec_shapes)} paths). Regenerate with "
            "`pnpm generate:openapi` in the gateway repo if it is stale.",
        )


if __name__ == "__main__":
    unittest.main()
