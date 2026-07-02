"""Single-bot state — one bot per install (Hummingbot runs one bot at a time).

There is no instance registry: an install runs at most one ``hbot`` bot. Its runtime state lives in::

    data/bot/
        meta.json     # config, type, name, db_path, started_at (db_path recorded once running)
        bot.pid       # pid of the detached engine process
        status.json   # latest on-demand snapshot written by the engine (SIGUSR1)
        bot.log       # child stdout/stderr (pre-logging + uncaught only; the structured log is primary)

The trades sqlite DB and the structured log are Hummingbot's own (``data/<name>.sqlite``,
``logs/logs_<name>.log``); we record their location in meta.json so readers don't re-derive it. For
multiple bots, use multiple installs/containers — the same way Hummingbot itself scales.
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from hummingbot import data_path, prefix_path


def bot_dir() -> Path:
    return Path(data_path()) / "bot"


def _meta_file() -> Path:
    return bot_dir() / "meta.json"


def _pid_file() -> Path:
    return bot_dir() / "bot.pid"


def _status_file() -> Path:
    return bot_dir() / "status.json"


def log_file() -> Path:
    """Child stdout/stderr capture (startup + uncaught; the structured log is the primary log)."""
    return bot_dir() / "bot.log"


def structured_log_file() -> Path:
    """Hummingbot's structured log for this bot (init_logging strategy_file_path == meta['name'])."""
    name = (read_meta() or {}).get("name") or "hummingbot"
    return Path(prefix_path()) / "logs" / f"logs_{name}.log"


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
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tail_lines(path: Path, n: int) -> List[str]:
    """Read the last ``n`` lines by seeking from the end — avoids loading the whole file."""
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


def exists() -> bool:
    return _meta_file().exists()


def read_meta() -> Optional[Dict[str, Any]]:
    if not _meta_file().exists():
        return None
    try:
        return json.loads(_meta_file().read_text())
    except json.JSONDecodeError:
        return None


def write_meta(meta: Dict[str, Any]) -> None:
    _atomic_write(_meta_file(), json.dumps(meta, indent=2, default=str))


def update_meta(**fields: Any) -> Dict[str, Any]:
    meta = read_meta() or {}
    meta.update(fields)
    write_meta(meta)
    return meta


def read_pid() -> Optional[int]:
    if not _pid_file().exists():
        return None
    try:
        return int(_pid_file().read_text().strip())
    except (ValueError, OSError):
        return None


def write_pid(pid: int) -> None:
    _atomic_write(_pid_file(), str(pid))


def clear_pid() -> None:
    if _pid_file().exists():
        _pid_file().unlink()


def running() -> bool:
    pid = read_pid()
    return pid is not None and pid_alive(pid)


def read_status() -> Optional[Dict[str, Any]]:
    if not _status_file().exists():
        return None
    try:
        return json.loads(_status_file().read_text())
    except json.JSONDecodeError:
        return None


def write_status(status: Dict[str, Any]) -> None:
    _atomic_write(_status_file(), json.dumps(status, indent=2, default=str))


def db_path() -> Optional[str]:
    return (read_meta() or {}).get("db_path")


def config_file_path() -> Optional[str]:
    return (read_meta() or {}).get("config_file_path")


def _loaded_file() -> Path:
    return bot_dir() / "loaded.json"


def read_loaded() -> Optional[Dict[str, Any]]:
    """The config `hbot import` (or the last `hbot start`) loaded — ``{"file", "type"}`` — or None.

    This is the "currently loaded strategy" the interactive client keeps: what `hbot start` runs when
    given no file, and what `hbot config` shows/edits when no bot is running.
    """
    if not _loaded_file().exists():
        return None
    try:
        return json.loads(_loaded_file().read_text())
    except json.JSONDecodeError:
        return None


def write_loaded(file: str, stype: str) -> None:
    _atomic_write(_loaded_file(), json.dumps({"file": file, "type": stype}, indent=2))


def clear_loaded() -> None:
    if _loaded_file().exists():
        _loaded_file().unlink()


def resolve_db_path() -> Optional[str]:
    """The current bot's trades sqlite DB: the engine-recorded path, else data/<name>.sqlite."""
    p = db_path()
    if p and Path(p).exists():
        return p
    name = (read_meta() or {}).get("name")
    return db_path_for(name) if name else None


def db_path_for(name: str) -> Optional[str]:
    """Trades DB for a named (possibly stopped) bot: data/<name>.sqlite, trying a dot-flattened variant."""
    for n in (name, name.replace(".", "_")):
        p = Path(data_path()) / f"{n}.sqlite"
        if p.exists():
            return str(p)
    return None


def structured_log_for(name: str) -> Optional[Path]:
    """Structured log for a named bot: logs/logs_<name>.log, trying a dot-flattened variant."""
    for n in (name, name.replace(".", "_")):
        p = Path(prefix_path()) / "logs" / f"logs_{n}.log"
        if p.exists():
            return p
    return None


def list_bots() -> List[str]:
    """Names of bots that have on-disk data (a trades DB and/or a structured log) — current or past."""
    names = set()
    dd = Path(data_path())
    if dd.exists():
        names |= {p.stem for p in dd.glob("*.sqlite")}
    ld = Path(prefix_path()) / "logs"
    if ld.exists():
        names |= {p.name[len("logs_"):-len(".log")] for p in ld.glob("logs_*.log")}
    return sorted(names)
