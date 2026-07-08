"""``hbot doctor`` — one-shot health check; the exit code IS the health signal.

Every check is a row: ``ok`` / ``warn`` / ``fail`` / ``skip`` plus a one-line detail with the
fix. Any ``fail`` exits 1 (ERROR); warns and skips exit 0 — they are advisories, not breakage.
Checks never crash the command: an unexpected exception becomes that check's ``fail`` row.

The checks are the failure modes that otherwise surface one at a time as confusing runtime
errors: a drifted clock silently rejecting signed exchange requests, a stale pidfile making
``stop`` wait its full timeout, a dangling loaded-config pointer, a keystore password that
doesn't unlock, missing compiled extensions after a bad build, a disk filling up under the
trades DB.
"""
import os
import shutil
import time
from pathlib import Path
from typing import Callable, List, Optional

from hummingbot.cli.output import ExitCode, emit, fail, json_option, render_table

REPO_ROOT = Path(__file__).resolve().parents[3]

NETWORK_TIMEOUT = 5.0
# Signed exchange APIs commonly allow ~5s of clock drift (recvWindow); our time sources have
# ~1s granularity plus network latency, so thresholds are deliberately forgiving.
CLOCK_WARN_S = 2.0
CLOCK_FAIL_S = 10.0
DISK_WARN_BYTES = 1 << 30    # 1 GiB
DISK_FAIL_BYTES = 100 << 20  # 100 MiB


def _row(check: str, status: str, detail: str) -> dict:
    return {"check": check, "status": status, "detail": detail}


# ── individual checks (each returns one row) ────────────────────────────────

def _install_row() -> dict:
    install = "docker" if os.environ.get("INSTALLATION_TYPE") == "docker" else "source"
    version = "unknown"
    try:
        version = (REPO_ROOT / "hummingbot" / "VERSION").read_text().strip()
    except OSError:
        pass
    import platform
    return _row("install", "ok", f"{install}, hummingbot {version}, python {platform.python_version()}")


def _extensions_row() -> dict:
    try:
        import hummingbot.core.clock  # noqa: F401  (a compiled Cython module)
        return _row("extensions", "ok", "compiled Cython extensions import")
    except ImportError as e:
        return _row("extensions", "fail",
                    f"compiled extensions missing/broken ({e}) — run `hbot update` or `make install`")


def _keystore_row() -> dict:
    from hummingbot.client.config.security import Security
    if Security.new_password_required():
        return _row("keystore", "ok", "none yet — the first password you use creates it")
    password = os.environ.get("HBOT_PASSWORD") or os.environ.get("CONFIG_PASSWORD")
    if not password:
        return _row("keystore", "skip", "exists; set HBOT_PASSWORD to verify it unlocks")
    from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
    if Security.login(ETHKeyFileSecretManger(password)):
        return _row("keystore", "ok", "password unlocks the keystore")
    return _row("keystore", "fail", "the provided password does NOT unlock the keystore")


def _remote_unix_time() -> Optional[float]:
    """Best-effort current UTC time from a public source, RTT-compensated; None if offline."""
    import json as _json
    import urllib.request
    try:
        t0 = time.time()
        with urllib.request.urlopen("https://api.kraken.com/0/public/Time",
                                    timeout=NETWORK_TIMEOUT) as resp:
            data = _json.loads(resp.read())
        return float(data["result"]["unixtime"]) + (time.time() - t0) / 2
    except Exception:
        pass
    try:
        from email.utils import parsedate_to_datetime
        req = urllib.request.Request("https://www.cloudflare.com", method="HEAD")
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            date_header = resp.headers.get("Date")
        if date_header:
            return parsedate_to_datetime(date_header).timestamp() + (time.time() - t0) / 2
    except Exception:
        pass
    return None


def _clock_row() -> dict:
    remote = _remote_unix_time()
    if remote is None:
        return _row("clock", "warn",
                    "could not reach a time source — offline? (trading needs network access)")
    skew = abs(time.time() - remote)
    detail = f"skew vs internet time ~{skew:.1f}s"
    if skew <= CLOCK_WARN_S:
        return _row("clock", "ok", detail)
    if skew <= CLOCK_FAIL_S:
        return _row("clock", "warn", f"{detail} — signed exchange requests may start failing; sync NTP")
    return _row("clock", "fail", f"{detail} — signed exchange requests WILL fail; sync your clock (NTP)")


def _disk_row() -> dict:
    from hummingbot.cli import bot
    target = bot.bot_dir().parent  # data/ — where the trades DBs grow
    usage = shutil.disk_usage(target if target.exists() else REPO_ROOT)
    free_gb = usage.free / (1 << 30)
    detail = f"{free_gb:.1f} GiB free for data/ and logs/"
    if usage.free < DISK_FAIL_BYTES:
        return _row("disk", "fail", f"{detail} — the trades DB and logs will fail to write")
    if usage.free < DISK_WARN_BYTES:
        return _row("disk", "warn", f"{detail} — running low")
    return _row("disk", "ok", detail)


def _bot_row() -> dict:
    from hummingbot.cli import bot
    if not bot.exists():
        return _row("bot", "ok", "no bot has been started")
    pid = bot.read_pid()
    if pid is None:
        return _row("bot", "ok", "no bot running")
    if bot.pid_alive(pid):
        return _row("bot", "ok", f"bot running (pid {pid})")
    return _row("bot", "warn",
                f"stale bot.pid (pid {pid} is dead) — harmless; cleared by the next start/stop")


def _loaded_row() -> dict:
    from hummingbot.cli import bot
    loaded = bot.read_loaded()
    if not loaded or not loaded.get("file"):
        return _row("loaded config", "ok", "none (create/import loads one)")
    from hummingbot.cli.strategy_configs import config_path
    file, stype = loaded["file"], loaded["type"]
    if config_path(stype, file).exists():
        return _row("loaded config", "ok", f"{file} ({stype})")
    return _row("loaded config", "warn",
                f"{file} ({stype}) is missing on disk — `hbot import <file>` to load another")


CHECKS: List[Callable[[], dict]] = [
    _install_row, _extensions_row, _keystore_row, _clock_row,
    _disk_row, _bot_row, _loaded_row,
]


def doctor(as_json: bool = json_option()) -> None:
    """Check the install's health; exit 0 = healthy, 1 = something needs fixing."""
    rows = []
    for check in CHECKS:
        try:
            rows.append(check())
        except Exception as e:  # a check may never crash the command
            rows.append(_row(check.__name__.strip("_").removesuffix("_row"), "fail",
                             f"check crashed: {e!r}"))
    healthy = all(r["status"] != "fail" for r in rows)
    payload = {"healthy": healthy, "checks": rows}
    emit(payload, render_table(rows, columns=["check", "status", "detail"], title="doctor"), as_json)
    if not healthy:
        fail("doctor found problems (see failed checks above)", ExitCode.ERROR)
