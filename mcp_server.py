"""MCP server for Hummingbot — a thin, faithful wrapper over the ``hbot`` CLI.

Each tool maps 1:1 onto an ``hbot`` command and runs it as a short subprocess. The CLI is
the substrate (headless engine, structured status, signal-based stop, stable exit codes);
this server only adds MCP transport so harnesses without a shell — or users who prefer
native tools — can drive the same bot. There is no tmux, no interactive client, and no
screen-scraping (see hbot-cli-vs-mcp-eval.md for why that substrate was replaced).

Configuration via environment variables (all optional):

* ``HBOT_BIN``      — the hbot executable to invoke. Defaults to ``bin/hbot-host`` next to
                      this file, which auto-detects a ``hummingbot`` conda env or a running
                      ``hummingbot`` Docker container.
* ``HBOT_PASSWORD`` — the keystore password, passed through to the CLI's environment.
                      Set it in the MCP server config; it is NEVER a tool argument.

Transport: **stdio only**, deliberately. The server's tools trade real money and MCP's HTTP
transports ship no auth; stdio keeps trading access behind credentials the OS already
manages (process spawn rights, the Docker socket). Every client reaches it by spawning a
process:

* source install — ``uv run --no-project --with "mcp>=1.10" python mcp_server.py``
  (see .mcp.json), or ``bin/hbot-mcp``.
* Docker — ``docker exec -i hummingbot hbot-mcp``: the harness on the host spawns the
  server inside the container and speaks stdio through the exec channel. Nothing to
  install on the host but the docker CLI; no port is ever opened.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent

# hbot's stable exit-code contract (hummingbot/cli/output.py). Branch on these, not on text.
EXIT_NAMES = {
    0: "SUCCESS",
    1: "ERROR",
    2: "NOT_FOUND",
    3: "NOT_RUNNING",
    4: "CONFIG_ERROR",
    5: "TIMEOUT",
}

# Floor for one subprocess call's kill ceiling; commands that take an operation --timeout
# get that value plus slack, so the CLI's own timeout always fires first (exit code 5).
# Tool timeout arguments are rejected above MAX_OP_TIMEOUT so a single MCP call can never
# block a harness indefinitely.
SUBPROCESS_TIMEOUT = 300
TIMEOUT_SLACK = 60
MAX_OP_TIMEOUT = 600

INSTRUCTIONS = """\
Operate a Hummingbot trading bot through the `hbot` CLI. Real money: prefer small sizes,
verify state after every mutating call, and stop the bot when the user is done.

Mental model:
- ONE bot per install. `start`/`deploy` fail if a bot is running unless replace=true.
- Three config types, one folder each: v1-strategy (conf/strategies/), v2-script
  (conf/scripts/), controller (conf/controllers/). File names are unique across folders,
  so a bare filename is unambiguous; the type is auto-detected.
- A config is first LOADED (create/import), then RUN (start). `deploy` does both in one
  call — it is the primitive to reach for when the user just wants a bot running.
- Controllers apply live-updatable field changes (~10s) while running via `config`.

The core loop:
  connections() → balance() → deploy(target, values) → status() → logs() → stop()
  Field discovery: create/deploy with missing required fields FAILS listing exactly the
  fields needed — that error is the documentation; don't invent field names.

Read results like this: every tool returns {ok, exit_code, exit_status, data|output, error}.
`data` is the parsed --json payload where the CLI supports it; `output` is compact Markdown
otherwise. Branch on ok/exit_status, never on prose.

Health: status() reporting running=true does NOT mean healthy — it includes a recent-errors
count; check it. history() also fetches balances, so it is the slowest call. When any tool
fails unexpectedly (or the user reports breakage), run doctor() FIRST — it pinpoints
keystore/clock/disk/stale-state problems and each failing check names its fix.

Secrets policy (strict):
- NEVER ask the user to paste API keys, private keys, or the keystore password into chat,
  and never accept them as tool inputs. Key entry is deliberately NOT a tool: have the user
  run `hbot connect <connector>` interactively in their own terminal (input is hidden and
  goes straight into the encrypted keystore).
- The keystore password comes from HBOT_PASSWORD in the MCP server's environment. If a tool
  fails with exit_status CONFIG_ERROR mentioning the password, tell the user to set
  HBOT_PASSWORD in their MCP config — do not ask for the password itself.
- On a brand-new install the first password used BECOMES the keystore password.
"""

mcp = FastMCP("hummingbot", instructions=INSTRUCTIONS)


def _hbot_bin() -> str:
    override = os.environ.get("HBOT_BIN")
    if override:
        return override
    return str(PROJECT_ROOT / "bin" / "hbot-host")


def _run_hbot(args: list, stdin_data: Optional[str] = None, json_output: bool = False,
              op_timeout: float = 0.0) -> dict:
    """Run one hbot command and map it to the uniform tool result.

    ``json_output`` appends ``--json`` and parses stdout into ``data``; otherwise stdout
    (compact Markdown) is returned verbatim as ``output``. ``op_timeout`` is the command's
    own --timeout value, used to raise the subprocess kill ceiling above it.

    The child NEVER inherits this process's stdin — that is the MCP JSON-RPC stream, and a
    stray read would corrupt the session. No piped input means /dev/null.
    """
    cmd = [_hbot_bin(), *[str(a) for a in args]]
    if json_output:
        cmd.append("--json")
    stdin_kwargs = ({"input": stdin_data} if stdin_data is not None
                    else {"stdin": subprocess.DEVNULL})
    kill_after = max(SUBPROCESS_TIMEOUT, op_timeout + TIMEOUT_SLACK)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=kill_after,
            cwd=PROJECT_ROOT,
            **stdin_kwargs,
        )
    except OSError as e:
        # Missing binary, no execute bit, HBOT_BIN pointing at a directory, ... — every
        # spawn failure must come back as the uniform result, never a raw traceback.
        return {
            "ok": False, "exit_code": -1, "exit_status": "NO_CLI",
            "data": None, "output": None,
            "error": f"cannot execute hbot ({cmd[0]}): {e}. Set HBOT_BIN to the hbot "
                     f"executable, or install the CLI (`make install`, or "
                     f"`make deploy && make link-cli` for Docker).",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False, "exit_code": -1, "exit_status": "CLIENT_TIMEOUT",
            "data": None, "output": None,
            "error": f"hbot did not return within {kill_after:g}s: {' '.join(cmd)}",
        }

    result = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "exit_status": EXIT_NAMES.get(proc.returncode, "UNKNOWN"),
        "data": None,
        "output": None,
        "error": proc.stderr.strip() or None,
    }
    stdout = proc.stdout.strip()
    if json_output and stdout:
        # Some commands emit their --json payload AND a nonzero exit (doctor: the checks
        # table plus health-as-exit-code) — parse whenever stdout parses. A broken payload
        # on a SUCCESSFUL exit is a broken contract and fails loudly; on a failed exit the
        # stdout is best-effort and returned as-is.
        try:
            result["data"] = json.loads(stdout)
        except ValueError:
            result["output"] = stdout
            if proc.returncode == 0:
                result["ok"] = False
                result["exit_status"] = "PROTOCOL_ERROR"
                result["error"] = f"hbot --json emitted unparseable output: {' '.join(cmd)}"
    else:
        result["output"] = stdout or None
    return result


def _set_args(values: Optional[dict]) -> tuple:
    """Encode a {field: value} dict as (extra_args, stdin) using --values-stdin (bulk fill)."""
    if not values:
        return [], None
    return ["--values-stdin"], json.dumps(values)


TYPE_FLAGS = {"v1-strategy": "--v1-strategy", "v2-script": "--v2-script", "controller": "--controller"}

# Literal in the tool signatures pushes the allowed values into the MCP schema, so clients
# reject a bad config_type before the call; this is the safety net for direct callers.
ConfigType = Literal["", "v1-strategy", "v2-script", "controller"]


def _type_args(config_type: str) -> list:
    """Map a config_type value to the CLI's disambiguation flag; raise on an unknown value."""
    if not config_type:
        return []
    flag = TYPE_FLAGS.get(config_type)
    if flag is None:
        raise ValueError(f"config_type must be one of {sorted(TYPE_FLAGS)} (got '{config_type}')")
    return [flag]


def _timeout_error(timeout: float) -> Optional[dict]:
    if timeout > MAX_OP_TIMEOUT:
        return _bad_argument(f"timeout must be <= {MAX_OP_TIMEOUT}s (got {timeout:g}) — "
                             f"one MCP call may not block the harness longer than that")
    return None


def _bad_argument(message: str) -> dict:
    return {"ok": False, "exit_code": -1, "exit_status": "BAD_ARGUMENT",
            "data": None, "output": None, "error": message}


# ── set up (connectors & funds) ──────────────────────────────────────────────

@mcp.tool()
def connections(connector: str = "", show_all: bool = False) -> dict:
    """Show connected connectors, list all connectable ones, or a connector's key fields.

    Read-only. With no arguments: the user's current connections (requires the keystore
    password, i.e. HBOT_PASSWORD). show_all=True: every connectable connector, no keys
    needed. Passing a connector shows which API-key fields it requires (also keys-free).

    Adding keys is deliberately NOT a tool — never accept keys in chat. Have the user run
    `hbot connect <connector>` interactively in their own terminal instead.
    """
    if connector:
        return _run_hbot(["connect", connector, "--fields"])
    if show_all:
        return _run_hbot(["connect", "--all"])
    return _run_hbot(["connect"])


@mcp.tool()
def balance(units_only: bool = False) -> dict:
    """Balances per connected connector with USD value; perps also show positions + net value.

    units_only=True skips the price fetch (token amounts only — faster).
    """
    args = ["balance"]
    if units_only:
        args.append("--units-only")
    return _run_hbot(args, json_output=True)


# ── create, load & configure ─────────────────────────────────────────────────

@mcp.tool()
def create(strategy: str, values: Optional[dict] = None, name: str = "",
           with_defaults: bool = False, config_type: ConfigType = "") -> dict:
    """Create a strategy/controller/script config file and load it (without starting).

    `values` fills fields ({field: value}); a missing required field fails with the exact
    list of fields needed — use that error for field discovery instead of guessing.
    with_defaults=True scaffolds defaults + blank required fields to fill via config().
    config_type is only needed when the strategy name exists under more than one type.
    Prefer deploy() when the goal is a RUNNING bot.
    """
    extra, stdin = _set_args(values)
    args = ["create", strategy, *_type_args(config_type), *extra]
    if name:
        args += ["--name", name]
    if with_defaults:
        args.append("--with-defaults")
    return _run_hbot(args, stdin_data=stdin)


@mcp.tool()
def import_config(config_file: str, config_type: ConfigType = "") -> dict:
    """Load an existing config file (from conf/strategies|scripts|controllers) as the
    current strategy, so config() can edit it and start() can run it.

    config_type is only needed when the file name exists under more than one type — the
    error will say so.
    """
    return _run_hbot(["import", config_file, *_type_args(config_type)])


@mcp.tool()
def config(key: Optional[str] = None, value: Optional[str] = None) -> dict:
    """View or set configuration — global client settings plus the loaded strategy's fields.

    No args: show everything. key only: read one field. key + value: set it (global keys
    win over strategy keys). On a RUNNING controller, live-updatable fields apply in ~10s;
    the reply says when a change takes effect.
    """
    if value is not None and key is None:
        return _bad_argument("a value requires a key — pass key and value to set a field")
    args = ["config"]
    if key is not None:
        args.append(key)
        if value is not None:
            args.append(value)
    return _run_hbot(args, json_output=True)


# ── run & control ────────────────────────────────────────────────────────────

@mcp.tool()
def deploy(target: str, values: Optional[dict] = None, name: str = "",
           replace: bool = False, timeout: float = 120.0, config_type: ConfigType = "") -> dict:
    """One shot: config → RUNNING bot. The primary way to launch.

    `target` is either an existing config file name (deployed as-is, `values` edits it
    first) or a strategy/controller/script name (a ready-to-run config is created; every
    required field must then be in `values` — a miss fails listing the missing fields).
    replace=True stops a currently running bot first. config_type disambiguates a name
    that exists under more than one type. Verify with status() afterwards.
    """
    if err := _timeout_error(timeout):
        return err
    extra, stdin = _set_args(values)
    args = ["deploy", target, *_type_args(config_type), *extra, "--timeout", timeout]
    if name:
        args += ["--name", name]
    if replace:
        args.append("--replace")
    return _run_hbot(args, stdin_data=stdin, json_output=True, op_timeout=timeout)


@mcp.tool()
def start(config_file: str = "", replace: bool = False, timeout: float = 120.0,
          config_type: ConfigType = "") -> dict:
    """Start a bot from a config file (type auto-detected), detached.

    With no config_file, runs the currently loaded config (from create/import). Fails if a
    bot is already running unless replace=True. config_type disambiguates a name that
    exists under more than one type. Verify with status() afterwards.
    """
    if err := _timeout_error(timeout):
        return err
    args = ["start"]
    if config_file:
        args.append(config_file)
    args += [*_type_args(config_type), "--timeout", timeout]
    if replace:
        args.append("--replace")
    return _run_hbot(args, json_output=True, op_timeout=timeout)


@mcp.tool()
def stop(force: bool = False, timeout: float = 30.0) -> dict:
    """Stop the running bot gracefully — cancels its open orders first.

    force=True SIGKILLs if still alive after `timeout` seconds (open orders may survive on
    the exchange — check afterwards). exit_status NOT_RUNNING means it was already stopped.
    """
    if err := _timeout_error(timeout):
        return err
    args = ["stop", "--timeout", timeout]
    if force:
        args.append("--force")
    return _run_hbot(args, json_output=True, op_timeout=timeout)


# ── observe ──────────────────────────────────────────────────────────────────

@mcp.tool()
def status() -> dict:
    """Run state, live strategy status, and a recent-errors count.

    running=true does NOT mean healthy — a bot can be alive and erroring; check the error
    count and read logs() when it is non-zero.
    """
    return _run_hbot(["status"], json_output=True)


@mcp.tool()
def logs(name: str = "", lines: int = 100) -> dict:
    """Trailing log lines (snapshot; there is no follow mode over MCP).

    With no name: the current bot. Pass a name (a config stem from a previous start) to
    read a past/stopped bot's log.
    """
    args = ["logs"]
    if name:
        args.append(name)
    args += ["--lines", lines]
    return _run_hbot(args, json_output=True)


@mcp.tool()
def history(name: str = "", days: Optional[float] = None) -> dict:
    """PnL, fees, and volume per market (the slowest call — it also fetches balances).

    With no name: the current bot. Pass a name to review a past/stopped bot indefinitely.
    """
    args = ["history"]
    if name:
        args.append(name)
    if days is not None:
        args += ["--days", days]
    return _run_hbot(args)


# ── maintain ─────────────────────────────────────────────────────────────────

@mcp.tool()
def doctor() -> dict:
    """Health-check the install; run this FIRST when any tool fails unexpectedly.

    data.checks rows (install, extensions, keystore, clock skew, disk, stale bot state,
    dangling loaded config, MCP server) each carry ok/warn/fail/skip plus a one-line fix;
    data.healthy is the verdict (an unhealthy run also returns exit_status ERROR).
    """
    return _run_hbot(["doctor"], json_output=True)


@mcp.tool()
def update(check: bool = True) -> dict:
    """Update the hbot software itself (source installs: git fast-forward + rebuild).

    check=True (the DEFAULT) only reports whether an update is available — safe anytime.
    check=False performs the update: refuses while a bot is running, on a diverged branch,
    and inside Docker (there it returns the host-side `docker compose pull` instructions —
    a container cannot replace its own image). A real update can take minutes when the
    compiled extensions rebuild.
    """
    args = ["update"]
    if check:
        args.append("--check")
    # A rebuild legitimately runs for minutes; raise the kill ceiling well above it.
    return _run_hbot(args, json_output=True, op_timeout=900)


if __name__ == "__main__":
    mcp.run()  # stdio only — see the module docstring for why there is no HTTP mode
