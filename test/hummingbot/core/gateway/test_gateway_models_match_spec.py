"""The models in connector/gateway/gateway.py must match the Gateway schemas they mirror.

Those six models are transcriptions: each field carries the camelCase alias of a Gateway
response field, and each is built by handing Gateway's response straight to pydantic. A
field Gateway stops sending therefore stops arriving — and because the transcription is
by hand, nothing here changes when Gateway's schema does.

hummingbot/core/gateway/gateway_models.py is the same schemas generated from Gateway's
OpenAPI spec rather than typed out, so this compares the hand-written mirrors against a
mechanical one. `make gateway-models` regenerates it; the first test below fails if the
committed copy is not what the vendored spec produces, which is what keeps the
comparison honest.

Adopting a Gateway change is two steps:

    cd ../gateway && pnpm generate:openapi
    cp ../gateway/openapi.json gateway-openapi.json
    make gateway-models
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hummingbot.connector.gateway.gateway import (
    AMMPoolInfo,
    AMMPositionDetail,
    AMMPositionInfo,
    CLMMPoolInfo,
    CLMMPositionInfo,
    TokenInfo,
)
from hummingbot.core.gateway import gateway_models

_REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = _REPO_ROOT / "gateway-openapi.json"
GENERATED_PATH = _REPO_ROOT / "hummingbot" / "core" / "gateway" / "gateway_models.py"

# Each hand-written mirror, paired with the generated model of the Gateway schema it is
# built from. Gateway's token entries are anonymous inside TokensResponse, so the
# generator names that item type `Token`.
MIRRORED_MODELS = [
    (TokenInfo, gateway_models.Token),
    (AMMPoolInfo, gateway_models.AmmPoolInfo),
    (CLMMPoolInfo, gateway_models.ClmmPoolInfo),
    (AMMPositionDetail, gateway_models.PositionDetail),
    (AMMPositionInfo, gateway_models.AmmPositionInfo),
    (CLMMPositionInfo, gateway_models.ClmmPositionInfo),
]

# Fields the position models add for this side's own use. They are filled in after
# construction, from token metadata, so Gateway never sends them and their absence from
# its schema is correct rather than drift.
LOCALLY_POPULATED_FIELDS = {"base_token", "quote_token"}


def _wire_names(model) -> set:
    """Field names as they travel on the wire — the alias where one is set."""
    return {(field.alias or name) for name, field in model.model_fields.items()}


class GatewayModelsMatchSpecTest(unittest.TestCase):
    def test_the_generated_models_match_the_vendored_spec(self):
        """Regenerating must reproduce the committed file exactly.

        The models are vendored so they import without a build step and so a Gateway
        change reads as a diff. That only holds while the committed copy is what the
        spec produces — a hand-edit, or a spec refreshed without rerunning the
        generator, and the comparisons below start checking against a shape Gateway
        never described.
        """
        # Generate to a real file rather than /dev/stdout. Under capture_output the
        # process's stdout is a pipe, so on Linux /dev/stdout resolves to
        # /proc/<pid>/fd/1 -> "pipe:[...]", which the generator then tries to open BY
        # NAME and cannot: FileNotFoundError on a path that is not a path. macOS
        # resolves it differently, so this passed locally and failed only in CI.
        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp) / "gateway_models.py"
            result = subprocess.run(
                [
                    sys.executable, "-m", "datamodel_code_generator",
                    "--input", str(SPEC_PATH),
                    "--input-file-type", "openapi",
                    "--openapi-scopes", "schemas",
                    "--output", str(generated),
                    "--output-model-type", "pydantic_v2.BaseModel",
                    "--snake-case-field",
                    # Matches setup.py's python_requires floor, not the interpreter
                    # running the tests: targeting 3.12 emits StrEnum, which 3.10 lacks.
                    "--target-python-version", "3.10",
                    "--disable-timestamp",
                    # Keeps `connector`/`network` as plain strings rather than baking
                    # Gateway's current roster into this client. See the Makefile.
                    "--ignore-enum-constraints",
                    "--formatters", "black",
                    "--formatters", "isort",
                    "--custom-file-header", "\n".join(GENERATED_PATH.read_text().splitlines()[:2]),
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"datamodel-codegen failed:\n{result.stderr}")
            self.assertEqual(
                generated.read_text(), GENERATED_PATH.read_text(),
                f"{GENERATED_PATH.name} is not what {SPEC_PATH.name} generates. "
                "Run `make gateway-models` and commit the result.",
            )

    def test_mirrored_models_only_declare_fields_gateway_sends(self):
        for mirror, generated in MIRRORED_MODELS:
            with self.subTest(model=mirror.__name__):
                missing = sorted(
                    _wire_names(mirror) - _wire_names(generated) - LOCALLY_POPULATED_FIELDS
                )
                self.assertFalse(
                    missing,
                    f"{mirror.__name__} declares {missing}, which Gateway's "
                    f"{generated.__name__} does not send. Those fields are populated from "
                    "Gateway's response, so they will be missing or default forever rather "
                    "than raising. Follow the rename, or drop them.",
                )
                # The reverse is deliberate: Gateway sends fields this side has no use
                # for, and pydantic drops them.

    def test_the_comparison_is_not_vacuous(self):
        """A mirror with no aliased fields would satisfy the subset check trivially."""
        for mirror, generated in MIRRORED_MODELS:
            with self.subTest(model=mirror.__name__):
                self.assertGreaterEqual(len(_wire_names(mirror)), 3, "Mirror looks empty")
                self.assertGreaterEqual(len(_wire_names(generated)), 3, "Generated model looks empty")


if __name__ == "__main__":
    unittest.main()
