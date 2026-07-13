from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


SOURCE_PATHS = (
    "conf/strategy_evolution.json",
    "conf/controllers/conf_pmm_mister_paper.yml",
    "conf/scripts/conf_pmm_mister_paper.yml",
    "controllers",
    "deploy/evolution",
    "hummingbot/strategy_v2/backtesting",
    "hummingbot/strategy_v2/evolution",
    "hummingbot/strategy_v2/executors",
    "scripts/check_strategy_evolution_health.py",
    "scripts/run_pmm_mister_paper.sh",
    "scripts/strategy_evolution_backup.py",
    "scripts/strategy_evolution_loop.py",
    "scripts/v2_with_controllers.py",
    "scripts/walk_forward_funding_arb.py",
    "scripts/walk_forward_pmm_mister.py",
    "scripts/walk_forward_supertrend.py",
    "test/hummingbot/strategy_v2/evolution",
)


def source_fingerprint(root: Path) -> str:
    root = root.resolve()
    digest = hashlib.sha256()
    for relative in SOURCE_PATHS:
        source = root / relative
        files = sorted(source.rglob("*")) if source.is_dir() else [source]
        for path in files:
            if not _include_source_file(path):
                continue
            digest.update(str(path.relative_to(root)).encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def runtime_identity(root: Path) -> dict[str, Any]:
    expected = os.environ.get("STRATEGY_EVOLUTION_SOURCE_SHA256", "").strip()
    return {
        "release_id": os.environ.get("STRATEGY_EVOLUTION_RELEASE_ID") or "development",
        "source_sha256": expected or source_fingerprint(root),
        "image_reference": os.environ.get("STRATEGY_EVOLUTION_IMAGE_REFERENCE") or None,
    }


def _include_source_file(path: Path) -> bool:
    if not path.is_file() or "__pycache__" in path.parts:
        return False
    if path.suffix in {".pyc", ".pyo", ".sqlite", ".log"}:
        return False
    if path.name.startswith("conf_evo_"):
        return False
    return path.stat().st_size <= 10 * 1024 * 1024
