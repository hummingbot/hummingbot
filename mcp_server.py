"""MCP server for managing Hummingbot v2 bots as detached TMUX sessions.

Each bot runs in its own ``tmux`` session named ``hb-<config-stem>``. The server
exposes MCP tools to deploy controllers, start/stop bots, tail their logs and read
the live status panel — so an assistant can operate a fleet of bots without a human
attaching to each terminal.

Configuration via environment variables (all optional):

* ``HB_PYTHON``     — absolute path to the Python interpreter of the ``hummingbot``
                      conda env. If unset, common conda locations are probed.
* ``HB_PROJECT_ROOT`` — Hummingbot checkout to operate on. Defaults to this file's dir.

Requirements: ``tmux`` on PATH, and (for ``open_terminal``) macOS with ``osascript``.
"""

import os
import platform
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(os.environ.get("HB_PROJECT_ROOT", Path(__file__).resolve().parent))
SESSION_PREFIX = "hb-"

# Timeouts (seconds) for the short, synchronous helper subprocesses.
TMUX_TIMEOUT = 10
PGREP_TIMEOUT = 5

# Bounds for log tailing so a tool call never returns an unbounded blob.
MAX_LOG_LINES = 2000

# Seconds to let the pane's interactive shell finish initializing before we type the
# launch command. On heavy prompts (oh-my-zsh + git status) send-keys sent too early is
# silently dropped, so the bot never starts. 0.5s is the empirical floor; 0.75s adds margin.
SHELL_SETTLE = float(os.environ.get("HB_SHELL_SETTLE", "0.75"))


def _resolve_hb_python() -> str:
    """Locate the hummingbot env interpreter.

    We invoke python by absolute path instead of ``conda run`` because on some setups
    ``conda run`` does not put the env's python on PATH (it can resolve to an unrelated
    active venv), and when the env is mounted as ``base`` then ``conda run -n hummingbot``
    builds a doubled, invalid path. ``HB_PYTHON`` always wins if set.
    """
    override = os.environ.get("HB_PYTHON")
    if override:
        return override
    candidates = [
        Path.home() / "anaconda3" / "envs" / "hummingbot" / "bin" / "python",
        Path.home() / "miniconda3" / "envs" / "hummingbot" / "bin" / "python",
        Path.home() / "miniforge3" / "envs" / "hummingbot" / "bin" / "python",
        Path("/opt/anaconda3/envs/hummingbot/bin/python"),
        Path("/opt/homebrew/anaconda3/envs/hummingbot/bin/python"),
        Path("/opt/miniconda3/envs/hummingbot/bin/python"),
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    # Fall back to the first well-known location; start_bot surfaces a clear error
    # if it does not exist, rather than failing opaquely inside tmux.
    return str(candidates[3])


HB_PYTHON = _resolve_hb_python()

mcp = FastMCP("hummingbot-manager")


# ── Subprocess helpers ───────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run a subprocess, converting environment failures into a CompletedProcess.

    A missing binary or a timeout would otherwise raise and crash the tool call; we
    surface them as returncode=-1 with a message on stderr so callers stay uniform.
    """
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, -1, "", f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, "", f"timed out after {timeout}s: {cmd[0]}")


def _run_tmux(*args: str) -> subprocess.CompletedProcess:
    return _run(["tmux", *args], TMUX_TIMEOUT)


def _session_exists(name: str) -> bool:
    return _run_tmux("has-session", "-t", name).returncode == 0


def _get_session_config(name: str) -> str | None:
    result = _run_tmux("show-environment", "-t", name, "HB_CONFIG")
    if result.returncode == 0 and "=" in result.stdout:
        return result.stdout.strip().split("=", 1)[1]
    return None


def _config_to_log_path(config_name: str) -> Path:
    stem = Path(config_name).stem
    return PROJECT_ROOT / "logs" / f"logs_{stem}.log"


def _capture_pane(name: str, lines: int = 40) -> str:
    result = _run_tmux("capture-pane", "-t", name, "-p", "-S", f"-{lines}")
    return result.stdout if result.returncode == 0 else ""


def _process_alive(name: str) -> bool:
    """True if the session's pane shell has a child process (i.e. the bot is running)."""
    pid_result = _run_tmux("list-panes", "-t", name, "-F", "#{pane_pid}")
    out = pid_result.stdout.strip().splitlines() if pid_result.returncode == 0 else []
    pane_pid = out[0].strip() if out else ""
    if not pane_pid:
        return False
    return _run(["pgrep", "-P", pane_pid], PGREP_TIMEOUT).returncode == 0


def _safe_stem(name: str) -> str | None:
    """Return the sanitized stem of a user-supplied name, or None if unsafe.

    Guards the filesystem paths built from run/config names against traversal
    (``..``) and separators, which would otherwise let a name escape conf/.
    """
    stem = Path(name).stem.strip()
    if not stem or stem in (".", "..") or "/" in name or "\\" in name:
        return None
    return stem


def _quickstart_cmd(config_file: str, password: str) -> str:
    """Build the shell command that launches the bot inside the tmux pane.

    The password is passed via the ``CONFIG_PASSWORD`` env var (which quickstart reads)
    rather than the ``-p`` flag, so it does not appear in the process argv / ``ps`` output.
    ``VIRTUAL_ENV``/``PYTHONPATH`` are cleared so the absolute-path interpreter is not
    shadowed by an active venv. Every interpolated value is shell-quoted.
    """
    return (
        f"VIRTUAL_ENV= PYTHONPATH= CONFIG_PASSWORD={shlex.quote(password)} "
        f"{shlex.quote(HB_PYTHON)} ./bin/hummingbot_quickstart.py "
        f"--v2 {shlex.quote(config_file)}"
    )


def _start_session(config_file: str, session_name: str, password: str) -> dict:
    """Create a detached TMUX session and launch the bot in it."""
    if _session_exists(session_name):
        return {"status": "error", "error": f"Session '{session_name}' already exists. Stop it first."}

    if not Path(HB_PYTHON).exists():
        return {
            "status": "error",
            "error": f"Hummingbot interpreter not found: {HB_PYTHON}. "
                     f"Set HB_PYTHON to the conda env's python.",
        }

    result = _run_tmux("new-session", "-d", "-s", session_name, "-c", str(PROJECT_ROOT))
    if result.returncode != 0:
        return {"status": "error", "error": f"Failed to create tmux session: {result.stderr.strip()}"}

    _run_tmux("set-environment", "-t", session_name, "HB_CONFIG", config_file)
    # Let the interactive shell settle so the launch command is not typed before the
    # prompt is ready (otherwise send-keys is dropped and the bot never starts).
    time.sleep(SHELL_SETTLE)
    _run_tmux("send-keys", "-t", session_name, _quickstart_cmd(config_file, password), "Enter")

    return {
        "status": "ok",
        "session_name": session_name,
        "config_file": config_file,
        "log_path": str(_config_to_log_path(config_file)),
    }


def _write_deploy_config(
    controllers: list[str],
    config_name: str,
    script_file_name: str,
    max_global_drawdown_quote: float | None,
    max_controller_drawdown_quote: float | None,
) -> dict:
    if not controllers:
        return {"status": "error", "error": "Must provide at least one controller config."}

    controllers_dir = PROJECT_ROOT / "conf" / "controllers"
    normalized = []
    for c in controllers:
        if not c.endswith(".yml"):
            c += ".yml"
        if _safe_stem(c) is None:
            return {"status": "error", "error": f"Invalid controller name: {c}"}
        if not (controllers_dir / c).exists():
            return {"status": "error", "error": f"Controller config not found: conf/controllers/{c}"}
        normalized.append(c)

    if _safe_stem(script_file_name) is None or not (PROJECT_ROOT / "scripts" / script_file_name).exists():
        return {"status": "error", "error": f"Script not found: scripts/{script_file_name}"}

    if not config_name.endswith(".yml"):
        config_name += ".yml"
    if _safe_stem(config_name) is None:
        return {"status": "error", "error": f"Invalid config name: {config_name}"}

    config_data = {
        "controllers_config": normalized,
        "script_file_name": script_file_name,
        "max_global_drawdown_quote": max_global_drawdown_quote,
        "max_controller_drawdown_quote": max_controller_drawdown_quote,
    }
    output_path = PROJECT_ROOT / "conf" / "scripts" / config_name
    with open(output_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    return {"status": "ok", "config_file": config_name, "path": str(output_path), "content": config_data}


def _tail(path: Path, n: int) -> list[str]:
    """Return the last ``n`` lines of a file without reading it fully into memory."""
    n = max(1, n)
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        data = b""
        block = 8192
        while pos > 0 and data.count(b"\n") <= n:
            read = min(block, pos)
            pos -= read
            f.seek(pos)
            data = f.read(read) + data
        lines = data.splitlines()[-n:]
    return [ln.decode("utf-8", "replace") for ln in lines]


# ── Deploy / start ─────────────────────────────────────────────────────────

@mcp.tool()
def deploy(
    controllers: list[str],
    run_name: str = "",
    password: str = "a",
    max_global_drawdown_quote: float | None = None,
    max_controller_drawdown_quote: float | None = None,
    script_file_name: str = "v2_with_controllers.py",
) -> dict:
    """Deploy one or more controllers as a new bot run.

    This is the high-level entry point: you say WHICH controllers to run and it
    builds the v2 deploy config for you with a UNIQUE name, so each run gets its own
    sqlite DB (data/{config}.sqlite) and log file (logs/logs_{config}.log) — easier to
    review in isolation. Then it starts the bot in a detached TMUX session.

    Args:
        controllers: Controller config filenames from conf/controllers/ (e.g. ["pmm_king_wld.yml"]).
        run_name: Optional label for this run. If omitted, a unique name is auto-generated
            from the first controller + timestamp (e.g. pmm_king_wld_0604_2103).
        password: Hummingbot password. Defaults to "a".
        max_global_drawdown_quote: Max global drawdown in quote. None = no limit.
        max_controller_drawdown_quote: Max per-controller drawdown in quote. None = no limit.
        script_file_name: v2 runner script. Defaults to v2_with_controllers.py.
    """
    if not controllers:
        return {"status": "error", "error": "Must provide at least one controller config."}

    if run_name:
        stem = _safe_stem(run_name)
        if stem is None:
            return {"status": "error", "error": f"Invalid run_name: {run_name}"}
    else:
        first_stem = _safe_stem(controllers[0]) or "run"
        stem = f"{first_stem}_{datetime.now().strftime('%m%d_%H%M')}"
    config_name = f"conf_{stem}.yml"
    session_name = f"{SESSION_PREFIX}{Path(config_name).stem}"

    created = _write_deploy_config(
        controllers, config_name, script_file_name,
        max_global_drawdown_quote, max_controller_drawdown_quote,
    )
    if created["status"] != "ok":
        return created

    started = _start_session(config_name, session_name, password)
    if started["status"] != "ok":
        return started

    db_stem = Path(config_name).stem
    return {
        "status": "ok",
        "session_name": session_name,
        "config_file": config_name,
        "controllers": created["content"]["controllers_config"],
        "log_path": str(_config_to_log_path(config_name)),
        "db_path": str(PROJECT_ROOT / "data" / f"{db_stem}.sqlite"),
        "note": "Unique DB + logs for this run. Attach with open_terminal, stop with stop_bot.",
    }


@mcp.tool()
def start_bot(config_file: str, session_name: str = "", password: str = "a") -> dict:
    """Start a bot from an EXISTING deploy config in conf/scripts/ (low-level).

    Prefer `deploy` for new runs (it builds a uniquely-named config for you). Use this
    when you want to re-run a specific existing conf/scripts/ file as-is.

    Args:
        config_file: Config filename in conf/scripts/ (e.g. conf_pmm_king_wld.yml).
        session_name: TMUX session name. Defaults to hb-{config_stem}.
        password: Hummingbot password. Defaults to "a".
    """
    if not config_file.endswith(".yml"):
        config_file += ".yml"
    if _safe_stem(config_file) is None:
        return {"status": "error", "error": f"Invalid config name: {config_file}"}
    if not (PROJECT_ROOT / "conf" / "scripts" / config_file).exists():
        return {"status": "error", "error": f"Config not found: conf/scripts/{config_file}"}

    name = session_name or f"{SESSION_PREFIX}{Path(config_file).stem}"
    return _start_session(config_file, name, password)


# ── Stop / cleanup ─────────────────────────────────────────────────────────

@mcp.tool()
def stop_bot(session_name: str, force: bool = False, cancel_timeout: int = 25) -> dict:
    """Stop a bot and ALWAYS clean up its TMUX session.

    Graceful by default: sends the hummingbot `stop` command (which cancels all open
    orders on the exchange) and waits for confirmation, then `exit`s the app, then
    kills the TMUX session so nothing is left behind. With force=True it skips the
    graceful cancel and kills the session immediately (orders may stay open!).

    Args:
        session_name: TMUX session name (e.g. hb-conf_pmm_king_wld).
        force: Skip graceful order-cancel and kill the session immediately.
        cancel_timeout: Seconds to wait for graceful stop confirmation before exiting.
    """
    if not _session_exists(session_name):
        return {"status": "error", "error": f"Session '{session_name}' not found."}

    method = "force-killed"
    if not force:
        _run_tmux("send-keys", "-t", session_name, "stop", "Enter")
        stopped = False
        for _ in range(max(1, cancel_timeout)):
            time.sleep(1.0)
            pane = _capture_pane(session_name, 40).lower()
            if "stopped successfully" in pane or "no active maker orders" in pane:
                stopped = True
                break
        _run_tmux("send-keys", "-t", session_name, "exit", "Enter")
        time.sleep(2.0)
        method = "graceful" if stopped else "graceful-timeout"

    # Guarantee cleanup: the session is always killed.
    _run_tmux("kill-session", "-t", session_name)
    return {"status": "ok", "method": method, "session_name": session_name, "cleaned_up": True}


@mcp.tool()
def kill_session(session_name: str) -> dict:
    """Force-kill a single TMUX session immediately (no graceful stop).

    Use to clean up a dead/zombie session, or one where the bot already crashed.
    Does NOT cancel exchange orders — use stop_bot for a running bot.
    """
    if not _session_exists(session_name):
        return {"status": "error", "error": f"Session '{session_name}' not found."}
    _run_tmux("kill-session", "-t", session_name)
    return {"status": "ok", "session_name": session_name, "killed": True}


@mcp.tool()
def kill_all_bots() -> dict:
    """Force-kill ALL Hummingbot (hb-) TMUX sessions. Cleanup sweep.

    Does NOT gracefully cancel orders. Use stop_bot per-session if bots are live.
    """
    result = _run_tmux("list-sessions", "-F", "#{session_name}")
    killed = []
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            name = line.strip()
            if name.startswith(SESSION_PREFIX):
                _run_tmux("kill-session", "-t", name)
                killed.append(name)
    return {"status": "ok", "killed": killed}


# ── Inspect ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_bots() -> dict:
    """List all Hummingbot TMUX sessions and whether each is actually running."""
    result = _run_tmux("list-sessions", "-F", "#{session_name}")
    if result.returncode != 0:
        return {"status": "ok", "sessions": []}

    sessions = []
    for line in result.stdout.strip().splitlines():
        name = line.strip()
        if not name.startswith(SESSION_PREFIX):
            continue
        alive = _process_alive(name)
        sessions.append({
            "session_name": name,
            "config": _get_session_config(name) or "unknown",
            "process_alive": alive,
            "state": "running" if alive else "idle/dead",
        })
    return {"status": "ok", "sessions": sessions}


@mcp.tool()
def open_terminal(session_name: str) -> dict:
    """Open a new macOS Terminal window attached to the bot's TMUX session.

    Lets you watch the live hummingbot UI directly. Detach with Ctrl-b then d
    (this does NOT stop the bot). macOS only.

    Args:
        session_name: TMUX session name (e.g. hb-conf_pmm_king_wld).
    """
    if platform.system() != "Darwin":
        return {
            "status": "error",
            "error": f"open_terminal is macOS-only. Attach manually: tmux attach -t {session_name}",
        }
    if not _session_exists(session_name):
        return {"status": "error", "error": f"Session '{session_name}' not found."}
    attach_cmd = f"tmux attach -t {shlex.quote(session_name)}"
    r = _run(
        [
            "osascript",
            "-e", 'tell application "Terminal" to activate',
            "-e", f'tell application "Terminal" to do script "{attach_cmd}"',
        ],
        TMUX_TIMEOUT,
    )
    if r.returncode != 0:
        return {"status": "error", "error": r.stderr.strip() or "osascript failed"}
    return {"status": "ok", "session_name": session_name, "opened": True}


@mcp.tool()
def read_logs(config_name: str = "", session_name: str = "", lines: int = 50) -> dict:
    """Read recent log lines from a Hummingbot bot.

    Args:
        config_name: Config filename to derive log path (e.g. conf_pmm_king_wld).
        session_name: Alternatively, provide session name to look up config.
        lines: Number of lines to read from end of log. Defaults to 50 (max 2000).
    """
    if not config_name and session_name:
        config_name = _get_session_config(session_name) or ""
    if not config_name:
        return {"status": "error", "error": "Provide config_name or a valid session_name."}

    log_path = _config_to_log_path(config_name)
    if not log_path.exists():
        return {"status": "error", "error": f"Log file not found: {log_path}"}

    lines = min(max(1, lines), MAX_LOG_LINES)
    try:
        tail = _tail(log_path, lines)
        return {
            "status": "ok",
            "log_path": str(log_path),
            "lines_returned": len(tail),
            "content": "\n".join(tail),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def bot_status(session_name: str) -> dict:
    """Get status of a Hummingbot bot TMUX session.

    Sends the hummingbot `status` command and returns the live strategy panel
    (curve, target/actual/gap, budgets, held inventory, resting orders) plus whether
    the process is alive. Requires a running strategy for the status panel to populate.

    Args:
        session_name: TMUX session name (e.g. hb-conf_pmm_king_wld).
    """
    if not _session_exists(session_name):
        return {"status": "error", "error": f"Session '{session_name}' not found."}

    alive = _process_alive(session_name)
    if alive:
        # Trigger a fresh status render, then read it back.
        _run_tmux("send-keys", "-t", session_name, "status", "Enter")
        time.sleep(2.0)

    return {
        "status": "ok",
        "session_name": session_name,
        "config": _get_session_config(session_name) or "unknown",
        "process_alive": alive,
        "terminal_output": _capture_pane(session_name, 60).strip(),
    }


@mcp.tool()
def list_controllers() -> dict:
    """List available controller config files in conf/controllers/."""
    controllers_dir = PROJECT_ROOT / "conf" / "controllers"
    if not controllers_dir.exists():
        return {"status": "error", "error": "conf/controllers/ directory not found."}
    configs = [f.name for f in sorted(controllers_dir.iterdir()) if f.suffix == ".yml"]
    return {"status": "ok", "controllers": configs}


@mcp.tool()
def create_config(
    controllers: list[str],
    config_name: str = "",
    script_file_name: str = "v2_with_controllers.py",
    max_global_drawdown_quote: float | None = None,
    max_controller_drawdown_quote: float | None = None,
) -> dict:
    """Create a deploy config in conf/scripts/ without starting it (low-level).

    Prefer `deploy` for new runs. Use this if you only want to write the config file.

    Args:
        controllers: Controller config filenames from conf/controllers/ (e.g. ["pmm_3.yml"]).
        config_name: Output filename in conf/scripts/. Defaults to conf_v2_{first_controller_stem}.yml.
        script_file_name: Script to use. Defaults to v2_with_controllers.py.
        max_global_drawdown_quote: Max global drawdown in quote. None = no limit.
        max_controller_drawdown_quote: Max per-controller drawdown in quote. None = no limit.
    """
    if not config_name:
        if not controllers:
            return {"status": "error", "error": "Must provide at least one controller config."}
        first_stem = _safe_stem(controllers[0])
        if first_stem is None:
            return {"status": "error", "error": f"Invalid controller name: {controllers[0]}"}
        config_name = f"conf_v2_{first_stem}.yml"
    return _write_deploy_config(
        controllers, config_name, script_file_name,
        max_global_drawdown_quote, max_controller_drawdown_quote,
    )


if __name__ == "__main__":
    mcp.run()
