"""Secure keystore-password resolution shared by commands that need to unlock the keystore.

A password is NEVER accepted on the command line (argv is visible via ps/`/proc`, shell history,
and agent tool logs). Resolution order:

    1. ``--password-stdin``  — read one line from stdin (automation, docker-login style)
    2. ``$HBOT_PASSWORD`` / ``$CONFIG_PASSWORD``  — env var (set once on the session)
    3. hidden interactive prompt  — only when stdin is a TTY (humans)

If none apply (non-interactive with no env/stdin), the command fails with a clear error.
"""
import getpass
import os
import sys

from hummingbot.cli.output import ExitCode, fail


def resolve_password(*, password_stdin: bool, json_output: bool, confirm: bool = False) -> str:
    if password_stdin:
        line = sys.stdin.readline()
        password = line.rstrip("\n")
        if not password:
            fail("no password received on stdin", ExitCode.CONFIG_ERROR, json_output=json_output)
        return password

    env = os.environ.get("HBOT_PASSWORD") or os.environ.get("CONFIG_PASSWORD")
    if env:
        return env

    if sys.stdin.isatty():
        password = getpass.getpass("Keystore password: ")
        if not password:
            fail("empty password", ExitCode.CONFIG_ERROR, json_output=json_output)
        if confirm and password != getpass.getpass("Confirm password: "):
            fail("passwords do not match", ExitCode.CONFIG_ERROR, json_output=json_output)
        return password

    fail("no password provided — use --password-stdin, set $HBOT_PASSWORD, or run interactively",
         ExitCode.CONFIG_ERROR, json_output=json_output)


def login(*, password_stdin: bool = False, json_output: bool = False, confirm: bool = False):
    """Resolve the keystore password, load the client config, and unlock Security.

    Returns ``(client_config_map, password)``; fails with a clear error on a bad password. The heavy
    config/security imports are deferred here so commands that don't authenticate stay fast to import.
    """
    from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    from hummingbot.client.config.security import Security
    password = resolve_password(password_stdin=password_stdin, json_output=json_output, confirm=confirm)
    client_config_map = load_client_config_map_from_file()
    if not Security.login(ETHKeyFileSecretManger(password)):
        fail("invalid password", ExitCode.CONFIG_ERROR, json_output=json_output)
    return client_config_map, password
