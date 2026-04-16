"""Auto-skip hummingbot tests superseded by installed sub-packages.

Sub-packages declare which hummingbot test paths they replace via
[tool.hummingbot.supersedes] in their pyproject.toml:

    [tool.hummingbot.supersedes]
    test_paths = ["test/hummingbot/data_feed/candles_feed"]
    exchanges = ["binance", "bybit", ...]

When a sub-package is importable, tests under its declared test_paths
are skipped — but only for exchanges/modules listed in its `exchanges`
array. Tests for HB-only modules keep running unconditionally.

To force all tests to run:
    pytest --run-superseded

Adding a new sub-package requires NO changes here — just add the
[tool.hummingbot.supersedes] section to the sub-package's pyproject.toml.
"""

import importlib
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def _discover_superseded_tests():
    """Scan sub-packages/*/pyproject.toml for [tool.hummingbot.supersedes]."""
    repo_root = Path(__file__).parent.parent
    sub_packages_dir = repo_root / "sub-packages"

    if not sub_packages_dir.is_dir():
        return []

    results = []
    for pkg_dir in sub_packages_dir.iterdir():
        if not pkg_dir.is_dir():
            continue
        pyproject = pkg_dir / "pyproject.toml"
        if not pyproject.exists():
            continue

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)

        supersedes = data.get("tool", {}).get("hummingbot", {}).get("supersedes", {})
        if not supersedes:
            continue

        # Determine the importable package name from project metadata
        project_name = data.get("project", {}).get("name", pkg_dir.name)
        # hb-candles-feed -> candles_feed
        import_name = project_name.removeprefix("hb-").replace("-", "_")

        # Check if the package is actually importable
        try:
            importlib.import_module(import_name)
        except ImportError:
            continue

        results.append(
            {
                "package": import_name,
                "test_paths": supersedes.get("test_paths", []),
                "exchanges": set(supersedes.get("exchanges", [])),
            }
        )

    return results


# Cache at module load time
_SUPERSEDED = _discover_superseded_tests()


def pytest_addoption(parser):
    parser.addoption(
        "--run-superseded",
        action="store_true",
        default=False,
        help="Run tests even when superseded by an installed sub-package",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-superseded"):
        return
    if not _SUPERSEDED:
        return

    for entry in _SUPERSEDED:
        pkg_name = entry["package"]
        test_paths = entry["test_paths"]
        exchanges = entry["exchanges"]

        skip_marker = pytest.mark.skip(reason=f"Superseded by {pkg_name} sub-package (use --run-superseded to force)")

        for item in items:
            item_path = str(item.path if hasattr(item, "path") else item.fspath)

            # Check if this test is under a superseded test path
            if not any(tp in item_path for tp in test_paths):
                continue

            # If no exchanges filter, skip everything under the path
            if not exchanges:
                item.add_marker(skip_marker)
                continue

            # Skip only if the test file matches a superseded exchange
            for exchange in exchanges:
                if f"{exchange}_" in item_path or f"/{exchange}/" in item_path:
                    item.add_marker(skip_marker)
                    break
