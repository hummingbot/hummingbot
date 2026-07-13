from __future__ import annotations

from pathlib import Path


DOCKER_WORKDIR = "/home/hummingbot"
SOURCE_OVERLAY_PATHS = (
    "scripts",
    "controllers",
    "test",
    "conf",
    "hummingbot/strategy_v2/backtesting",
    "hummingbot/strategy_v2/evolution",
    "hummingbot/strategy_v2/executors",
    "hummingbot/strategy_v2/routers",
)


def docker_source_paths(root: Path) -> list[tuple[str, Path]]:
    return [
        (relative, (root / relative).resolve())
        for relative in SOURCE_OVERLAY_PATHS
        if (root / relative).exists()
    ]


def docker_source_mounts(root: Path) -> list[str]:
    """Overlay editable Python/config/test trees without hiding image C extensions."""
    arguments: list[str] = []
    for relative, source in docker_source_paths(root):
        arguments.extend(["-v", f"{source}:{DOCKER_WORKDIR}/{relative}:ro"])
    return arguments
