"""``hbot start`` — launch a single bot detached and return its instance id."""
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer

from hummingbot import prefix_path
from hummingbot.cli.instances import Instance, tail_lines
from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


def _log_tail(instance: Instance, lines: int = 20) -> str:
    # Logged startup errors go to the structured log; pre-logging/uncaught output goes to bot.log.
    combined = tail_lines(instance.structured_log_file, lines) + tail_lines(instance.log_file, lines)
    return "\n".join(combined[-lines:])


def start(
    file: str = typer.Argument(..., help="Config file name for the selected type."),
    v1: bool = typer.Option(False, "--v1", help="V1 strategy config (conf/strategies)."),
    v2: bool = typer.Option(False, "--v2", help="V2 script config (conf/scripts)."),
    controller: bool = typer.Option(
        False, "--controller", help="V2 controller config (conf/controllers); run via the generic V2 runner."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    name: Optional[str] = typer.Option(
        None, "--name", help="Instance id. Defaults to the config file's base name."),
    auto_set_permissions: Optional[str] = typer.Option(
        None, "--auto-set-permissions", help="user:group to chown conf/data/logs (Docker)."),
    timeout: float = typer.Option(120.0, "--timeout", help="Seconds to wait for the bot to start."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Start a bot in the background; prints the instance id once it is running."""
    from hummingbot.cli.strategy_configs import config_path, validate_controller, wrap_controller_as_v2
    chosen = [t for t, on in (("v1", v1), ("v2", v2), ("controller", controller)) if on]
    if len(chosen) != 1:
        fail("specify exactly one of --v1 / --v2 / --controller", ExitCode.CONFIG_ERROR, json_output=json_output)
    stype = chosen[0]

    if not config_path(stype, file).exists():
        fail(f"{stype} config not found: {file}", ExitCode.NOT_FOUND, json_output=json_output)

    name = name or Path(file).stem
    instance = Instance(name)
    if instance.is_running():
        fail(f"instance '{name}' is already running (pid {instance.read_pid()})",
             ExitCode.ERROR, json_output=json_output)

    # Map the selected type to what the engine consumes: v1 -> config_file_name, v2 -> v2 conf.
    # A controller can't run standalone, so wrap it in a generic V2 runner config and start that.
    config_file_name: Optional[str] = None
    v2_conf: Optional[str] = None
    if stype == "v1":
        config_file_name = file
    elif stype == "v2":
        v2_conf = file
    else:
        try:
            validate_controller(config_path("controller", file))
        except Exception as e:
            fail(f"invalid controller config: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
        v2_conf = wrap_controller_as_v2(file)

    # Resolve and validate the password up front so failures are immediate (not buried in the
    # detached log). The password is passed to the child via env, never on argv.
    _, password = login(password_stdin=password_stdin, json_output=json_output)

    instance.dir.mkdir(parents=True, exist_ok=True)
    instance.write_meta({
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
    log_handle = open(instance.log_file, "ab")
    proc = subprocess.Popen(
        cmd, cwd=prefix_path(), stdin=subprocess.DEVNULL,
        stdout=log_handle, stderr=log_handle, start_new_session=True, env=env)
    log_handle.close()  # the child holds its own dup'd fd
    instance.write_pid(proc.pid)
    instance.update_meta(pid=proc.pid)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            instance.clear_pid()
            fail(f"bot exited during startup (rc={proc.returncode}). Recent log:\n{_log_tail(instance)}",
                 ExitCode.ERROR, json_output=json_output)
        engine = (instance.read_status() or {}).get("engine") or {}
        if engine.get("strategy_running"):
            break
        time.sleep(1.0)
    else:
        fail(f"timed out after {timeout:g}s waiting for '{name}' to start (pid {proc.pid} still booting)",
             ExitCode.TIMEOUT, json_output=json_output)

    result = {"ok": True, "name": name, "pid": proc.pid, "status": "running"}
    if json_output:
        print_json(result)
    else:
        typer.echo(f"Started '{name}' (pid {proc.pid}). "
                   f"Use `hbot status {name}` to monitor, `hbot stop {name}` to stop.")
