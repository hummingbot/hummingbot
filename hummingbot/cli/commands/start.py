"""``hbot start`` — launch the bot detached (one bot per install)."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer

from hummingbot import prefix_path
from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


def _log_tail(lines: int = 20) -> str:
    # Logged startup errors go to the structured log; pre-logging/uncaught output goes to bot.log.
    combined = bot.tail_lines(bot.structured_log_file(), lines) + bot.tail_lines(bot.log_file(), lines)
    return "\n".join(combined[-lines:])


def _replace_running(timeout: float, json_output: bool) -> None:
    """Gracefully stop the currently-running bot (so --replace can start a new one)."""
    pid = bot.read_pid()
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        bot.clear_pid()
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not bot.pid_alive(pid):
            bot.clear_pid()
            return
        time.sleep(0.5)
    fail(f"--replace: the running bot (pid {pid}) did not stop within {timeout:g}s; "
         f"run `hbot stop --force` and retry", ExitCode.TIMEOUT, json_output=json_output)


def start(
    file: str = typer.Argument(..., help="Config file name (its type is detected from conf/strategies|scripts|controllers)."),
    v1: bool = typer.Option(False, "--v1-strategy", help="Force V1 strategy type (only needed if the name collides across types)."),
    v2: bool = typer.Option(False, "--v2-script", help="Force V2 script type (only needed if the name collides across types)."),
    controller: bool = typer.Option(
        False, "--controller", help="Force controller type (only needed if the name collides across types)."),
    replace: bool = typer.Option(
        False, "--replace", help="If a bot is already running, stop it first, then start this one."),
    foreground: bool = typer.Option(
        False, "--foreground", help="Run the bot in the foreground (use as a container's main process)."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    auto_set_permissions: Optional[str] = typer.Option(
        None, "--auto-set-permissions", help="user:group to chown conf/data/logs (Docker)."),
    timeout: float = typer.Option(120.0, "--timeout", help="Seconds to wait for the bot to start."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Start a bot from a config file (type auto-detected).

    One bot per install — fails if one is already running. The type is detected from the conf dir
    holding the file; a --v1-strategy/--v2-script/--controller flag is only needed when a legacy name
    exists under more than one type. By default the bot runs detached (the command returns); pass
    --foreground to run it in the foreground, e.g. as a Docker container's main process."""
    # Same filename->type resolution as `strategy set/show-config/clone`: a flag forces the type, else
    # it's detected from the conf dirs (names are unique across types).
    from hummingbot.cli.commands._common import one_type
    from hummingbot.cli.strategy_configs import (
        config_path,
        resolve_config_type,
        validate_controller,
        wrap_controller_as_v2,
    )
    try:
        stype = resolve_config_type(file, one_type(v1, v2, controller, json_output, required=False))
    except FileNotFoundError as e:
        fail(str(e), ExitCode.NOT_FOUND, json_output=json_output)
    except ValueError as e:
        fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)

    if bot.running():
        if not replace:
            fail(f"a bot is already running (pid {bot.read_pid()}); stop it first or pass --replace "
                 f"(one bot per install)", ExitCode.ERROR, json_output=json_output)
        _replace_running(timeout=30.0, json_output=json_output)

    # Map the selected type to what the engine consumes. A controller can't run standalone, so generate
    # a v2 loader config and run that; the loader's stem becomes the bot's DB/log name.
    config_file_name: Optional[str] = None
    v2_conf: Optional[str] = None
    if stype == "v1-strategy":
        config_file_name = file
    elif stype == "v2-script":
        v2_conf = file
    else:
        try:
            validate_controller(config_path("controller", file))
        except Exception as e:
            fail(f"invalid controller config: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
        v2_conf = wrap_controller_as_v2(file)

    # The bot's name == the strategy file Hummingbot runs (the loader for controllers); this is what
    # names the structured log and the trades DB, so logs/trades/history line up.
    name = Path(v2_conf or config_file_name).stem

    # Resolve and validate the password up front so failures are immediate (not buried in the
    # detached log). The password is passed to the child via env, never on argv.
    _, password = login(password_stdin=password_stdin, json_output=json_output)

    bot.bot_dir().mkdir(parents=True, exist_ok=True)
    bot.write_meta({
        "name": name,
        "type": stype,
        "file": file,
        "config": config_file_name,
        "script_config": v2_conf,
        "started_at": time.time(),
    })

    cmd = [sys.executable, "-m", "hummingbot.cli.engine", "--name", name]
    if config_file_name:
        cmd += ["--config", config_file_name]
    if v2_conf:
        cmd += ["--script-config", v2_conf]
    if auto_set_permissions:
        cmd += ["--auto-set-permissions", auto_set_permissions]

    env = dict(os.environ, HBOT_PASSWORD=password)

    if foreground:
        # Replace this process with the engine so the bot runs in the FOREGROUND — the right shape for a
        # container's main process: the bot IS PID 1, so `docker stop` -> SIGTERM -> the engine's graceful
        # shutdown (cancels orders). os.exec* keeps the same PID, so the pid we record is the engine's;
        # stdout/stderr stay attached to the terminal/container (visible via `docker logs`).
        bot.write_pid(os.getpid())
        bot.update_meta(pid=os.getpid())
        os.chdir(prefix_path())
        os.execve(sys.executable, cmd, env)  # never returns

    _spawn_detached(cmd, env, name, timeout, json_output)


def _spawn_detached(cmd: list, env: dict, name: str, timeout: float, json_output: bool) -> None:
    """Launch the engine detached, wait until its strategy is running, and report — or fail with the
    recent log if it exits during startup / times out."""
    log_handle = open(bot.log_file(), "wb")  # fresh per run (startup/uncaught only)
    proc = subprocess.Popen(
        cmd, cwd=prefix_path(), stdin=subprocess.DEVNULL,
        stdout=log_handle, stderr=log_handle, start_new_session=True, env=env)
    log_handle.close()  # the child holds its own dup'd fd
    bot.write_pid(proc.pid)
    bot.update_meta(pid=proc.pid)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            bot.clear_pid()
            fail(f"bot exited during startup (rc={proc.returncode}). Recent log:\n{_log_tail()}",
                 ExitCode.ERROR, json_output=json_output)
        engine = (bot.read_status() or {}).get("engine") or {}
        if engine.get("strategy_running"):
            break
        time.sleep(1.0)
    else:
        fail(f"timed out after {timeout:g}s waiting for the bot to start (pid {proc.pid} still booting)",
             ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json({"ok": True, "name": name, "pid": proc.pid, "status": "running"})
    else:
        typer.echo(f"Started '{name}' (pid {proc.pid}). Use `hbot status` to monitor, `hbot stop` to stop.")
