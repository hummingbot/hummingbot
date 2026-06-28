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
