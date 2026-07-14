from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType


def bootstrap_hummingbot_namespace(root: Path) -> None:
    """Load pure routing modules without importing the full trading runtime."""
    if "hummingbot" in sys.modules:
        return
    package = ModuleType("hummingbot")
    package.__package__ = "hummingbot"
    package.__path__ = [str(root / "hummingbot")]  # type: ignore[attr-defined]
    sys.modules["hummingbot"] = package
