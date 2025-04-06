import subprocess
import sys


class CommandError(Exception):
    """
    Error raised when a command being executed returns an error
    """


def execute(command, exit_codes=None):
    """Execute provided command returning the stdout
    Args:
        command (list[str]): list of tokens to execute as your command.
        exit_codes (list[int]): exit codes which do not indicate error.
        subprocess_mod (module): Defaults to pythons subprocess module but you can optionally pass
        in another. This is mostly for testing purposes
    Returns:
        str - Stdout of the command passed in. This will be Unicode for python < 3. Str for python 3
    Raises:
        ValueError if there is a error running the command
    """
    if exit_codes is None:
        exit_codes = [0]

    stdout_pipe = subprocess.PIPE
    process = subprocess.Popen(command, stdout=stdout_pipe, stderr=stdout_pipe)
    try:
        stdout, stderr = process.communicate()
    except OSError:
        sys.stderr.write(
            " ".join(
                [
                    (
                        cmd.decode(sys.getfilesystemencoding())
                        if isinstance(cmd, bytes)
                        else cmd
                    )
                    for cmd in command
                ]
            )
        )
        raise

    stderr = _ensure_unicode(stderr)
    if process.returncode not in exit_codes:
        raise CommandError(stderr)

    return _ensure_unicode(stdout), stderr


def run_command_for_code(command):
    """
    Returns command's exit code.
    """
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        process.communicate()
    except FileNotFoundError:
        return 1
    return process.returncode


def _ensure_unicode(text):
    """
    Ensures the text passed in becomes unicode
    Args:
        text (str|unicode)
    Returns:
        unicode
    """
    if isinstance(text, bytes):
        return text.decode(sys.getfilesystemencoding(), "replace")
    return text
