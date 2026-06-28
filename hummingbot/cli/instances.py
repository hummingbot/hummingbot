"""Per-bot instance registry: the local files that back start/stop/status/logs.

Layout for an instance named ``<name>``::

    data/instances/<name>/
        meta.json     # static metadata: config, db path, pid, started_at
        bot.pid       # pid of the detached engine process
        status.json   # latest snapshot written by the running engine
        bot.log       # child stdout/stderr

The trades sqlite DB is recorded in ``meta.json`` (``db_path``) by the engine once the
strategy is running, so reader commands don't need to guess Hummingbot's naming.
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from hummingbot import data_path

INSTANCES_DIRNAME = "instances"


def instances_root() -> Path:
    return Path(data_path()) / INSTANCES_DIRNAME


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def pid_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` currently exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user.
        return True
    return True


def tail_lines(path: Path, n: int) -> List[str]:
    """Read the last ``n`` lines of ``path`` by seeking from the end — avoids loading the whole file."""
    if n <= 0 or not path.exists():
        return []
    with open(path, "rb") as f:
        f.seek(0, 2)
        remaining = f.tell()
        block = 8192
        data = b""
        while remaining > 0 and data.count(b"\n") <= n:
            step = min(block, remaining)
            remaining -= step
            f.seek(remaining)
            data = f.read(step) + data
    return data.decode("utf-8", errors="replace").splitlines()[-n:]


class Instance:
    def __init__(self, name: str):
        if not name or "/" in name or name in (".", ".."):
            raise ValueError(f"Invalid instance name: {name!r}")
        self.name = name
        self.dir = instances_root() / name

    # --- file paths ---
    @property
    def meta_file(self) -> Path:
        return self.dir / "meta.json"

    @property
    def pid_file(self) -> Path:
        return self.dir / "bot.pid"

    @property
    def status_file(self) -> Path:
        return self.dir / "status.json"

    @property
    def log_file(self) -> Path:
        return self.dir / "bot.log"

    @property
    def structured_log_file(self) -> Path:
        # The engine's init_logging(strategy_file_path=name) writes here (conf/hummingbot_logs.yml).
        from hummingbot import prefix_path
        return Path(prefix_path()) / "logs" / f"logs_{self.name}.log"

    # --- existence / liveness ---
    def exists(self) -> bool:
        return self.meta_file.exists()

    def read_pid(self) -> Optional[int]:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def is_running(self) -> bool:
        pid = self.read_pid()
        return pid is not None and pid_alive(pid)

    # --- reads ---
    def read_meta(self) -> Optional[Dict[str, Any]]:
        if not self.meta_file.exists():
            return None
        return json.loads(self.meta_file.read_text())

    def read_status(self) -> Optional[Dict[str, Any]]:
        if not self.status_file.exists():
            return None
        try:
            return json.loads(self.status_file.read_text())
        except json.JSONDecodeError:
            return None

    def db_path(self) -> Optional[str]:
        meta = self.read_meta() or {}
        return meta.get("db_path")

    def config_file_path(self) -> Optional[str]:
        meta = self.read_meta() or {}
        return meta.get("config_file_path")

    # --- writes ---
    def write_meta(self, meta: Dict[str, Any]) -> None:
        _atomic_write(self.meta_file, json.dumps(meta, indent=2, default=str))

    def update_meta(self, **fields: Any) -> Dict[str, Any]:
        meta = self.read_meta() or {}
        meta.update(fields)
        self.write_meta(meta)
        return meta

    def write_pid(self, pid: int) -> None:
        _atomic_write(self.pid_file, str(pid))

    def write_status(self, status: Dict[str, Any]) -> None:
        _atomic_write(self.status_file, json.dumps(status, indent=2, default=str))

    def clear_pid(self) -> None:
        if self.pid_file.exists():
            self.pid_file.unlink()


def list_instances() -> List[Instance]:
    root = instances_root()
    if not root.exists():
        return []
    return [Instance(d.name) for d in sorted(root.iterdir())
            if d.is_dir() and (d / "meta.json").exists()]
