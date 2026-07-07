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

Run: ``uv run --with mcp python mcp_server.py`` (see .mcp.json).
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

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
SUBPROCESS_TIMEOUT = 300
TIMEOUT_SLACK = 60

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
count; check it. history() also fetches balances, so it is the slowest call.

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
    except FileNotFoundError:
        return {
            "ok": False, "exit_code": -1, "exit_status": "NO_CLI",
            "data": None, "output": None,
            "error": f"hbot executable not found: {cmd[0]}. Set HBOT_BIN or install the CLI "
                     f"(`make install`, or `make deploy && make link-cli` for Docker).",
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
    if json_output and proc.returncode == 0:
        try:
            result["data"] = json.loads(stdout)
        except ValueError:
            result["output"] = stdout or None
    else:
        result["output"] = stdout or None
    return result


def _set_args(values: Optional[dict]) -> tuple:
    """Encode a {field: value} dict as (extra_args, stdin) using --values-stdin (bulk fill)."""
    if not values:
        return [], None
    return ["--values-stdin"], json.dumps(values)


TYPE_FLAGS = {"v1-strategy": "--v1-strategy", "v2-script": "--v2-script", "controller": "--controller"}


def _type_args(config_type: str) -> list:
    """Map a config_type value to the CLI's disambiguation flag; raise on an unknown value."""
    if not config_type:
        return []
    flag = TYPE_FLAGS.get(config_type)
    if flag is None:
        raise ValueError(f"config_type must be one of {sorted(TYPE_FLAGS)} (got '{config_type}')")
    return [flag]


def _bad_argument(message: str) -> dict:
    return {"ok": False, "exit_code": -1, "exit_status": "BAD_ARGUMENT",
            "data": None, "output": None, "error": message}


# ── set up (connectors & funds) ──────────────────────────────────────────────

@mcp.tool()
def connections(connector: str = "", show_fields: bool = False, show_all: bool = False) -> dict:
    """Show connected connectors, list all connectable ones, or a connector's key fields.

    Read-only. With no arguments: the user's current connections (requires the keystore
    password, i.e. HBOT_PASSWORD). show_all=True: every connectable connector, no keys
    needed. Passing a connector shows which API-key fields it requires.

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
           with_defaults: bool = False, config_type: str = "") -> dict:
    """Create a strategy/controller/script config file and load it (without starting).

    `values` fills fields ({field: value}); a missing required field fails with the exact
    list of fields needed — use that error for field discovery instead of guessing.
    with_defaults=True scaffolds defaults + blank required fields to fill via config().
    config_type ('v1-strategy'|'v2-script'|'controller') is only needed when the strategy
    name exists under more than one type. Prefer deploy() when the goal is a RUNNING bot.
    """
    try:
        type_args = _type_args(config_type)
    except ValueError as e:
        return _bad_argument(str(e))
    extra, stdin = _set_args(values)
    args = ["create", strategy, *type_args, *extra]
    if name:
        args += ["--name", name]
    if with_defaults:
        args.append("--with-defaults")
    return _run_hbot(args, stdin_data=stdin)


@mcp.tool()
def import_config(config_file: str, config_type: str = "") -> dict:
    """Load an existing config file (from conf/strategies|scripts|controllers) as the
    current strategy, so config() can edit it and start() can run it.

    config_type ('v1-strategy'|'v2-script'|'controller') is only needed when the file name
    exists under more than one type — the error will say so.
    """
    try:
        type_args = _type_args(config_type)
    except ValueError as e:
        return _bad_argument(str(e))
    return _run_hbot(["import", config_file, *type_args])


@mcp.tool()
def config(key: str = "", value: str = "") -> dict:
    """View or set configuration — global client settings plus the loaded strategy's fields.

    No args: show everything. key only: read one field. key + value: set it (global keys
    win over strategy keys). On a RUNNING controller, live-updatable fields apply in ~10s;
    the reply says when a change takes effect.
    """
    args = ["config"]
    if key:
        args.append(key)
        if value:
            args.append(value)
    return _run_hbot(args, json_output=True)


# ── run & control ────────────────────────────────────────────────────────────

@mcp.tool()
def deploy(target: str, values: Optional[dict] = None, name: str = "",
           replace: bool = False, timeout: float = 120.0, config_type: str = "") -> dict:
    """One shot: config → RUNNING bot. The primary way to launch.

    `target` is either an existing config file name (deployed as-is, `values` edits it
    first) or a strategy/controller/script name (a ready-to-run config is created; every
    required field must then be in `values` — a miss fails listing the missing fields).
    replace=True stops a currently running bot first. config_type
    ('v1-strategy'|'v2-script'|'controller') disambiguates a name that exists under more
    than one type. Verify with status() afterwards.
    """
    try:
        type_args = _type_args(config_type)
    except ValueError as e:
        return _bad_argument(str(e))
    extra, stdin = _set_args(values)
    args = ["deploy", target, *type_args, *extra, "--timeout", timeout]
    if name:
        args += ["--name", name]
    if replace:
        args.append("--replace")
    return _run_hbot(args, stdin_data=stdin, json_output=True, op_timeout=timeout)


@mcp.tool()
def start(config_file: str = "", replace: bool = False, timeout: float = 120.0,
          config_type: str = "") -> dict:
    """Start a bot from a config file (type auto-detected), detached.

    With no config_file, runs the currently loaded config (from create/import). Fails if a
    bot is already running unless replace=True. config_type
    ('v1-strategy'|'v2-script'|'controller') disambiguates a name that exists under more
    than one type. Verify with status() afterwards.
    """
    try:
        type_args = _type_args(config_type)
    except ValueError as e:
        return _bad_argument(str(e))
    args = ["start"]
    if config_file:
        args.append(config_file)
    args += [*type_args, "--timeout", timeout]
    if replace:
        args.append("--replace")
    return _run_hbot(args, json_output=True, op_timeout=timeout)


@mcp.tool()
def stop(force: bool = False, timeout: float = 30.0) -> dict:
    """Stop the running bot gracefully — cancels its open orders first.

    force=True SIGKILLs if still alive after `timeout` seconds (open orders may survive on
    the exchange — check afterwards). exit_status NOT_RUNNING means it was already stopped.
    """
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


if __name__ == "__main__":
    mcp.run()
