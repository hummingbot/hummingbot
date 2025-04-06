"""Provide a readline wrapper to control a subprocess."""

import sys
import ctypes
import signal
import builtins
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import compat

if compat.platform == "darwin":
    import fcntl


def rlwrap_process(args, prompt_control, use_stderr=False):
    assert len(prompt_control) == 1
    # Start process
    process = subprocess.Popen(
        args,
        bufsize=0,
        universal_newlines=True,
        stdin=subprocess.PIPE,
        **{"stderr" if use_stderr else "stdout": subprocess.PIPE},
    )
    # Readline wrapping
    return _rlwrap(process, prompt_control, use_stderr)


def _rlwrap(process, prompt_control, use_stderr=False):
    # Get source and destination
    source = process.stderr if use_stderr else process.stdout
    dest = sys.stderr if use_stderr else sys.stdout

    # Check prompt control
    assert len(prompt_control) == 1

    # Run background task
    with ThreadPoolExecutor(1) as executor:
        future = executor.submit(wait_for_prompt, source, dest, prompt_control)

        # Loop over prompts
        while process.poll() is None:
            # Get prompt
            try:
                prompt = future.result()
            except KeyboardInterrupt:
                process.send_signal(signal.SIGINT)
                continue
            except EOFError:
                break
            else:
                future = executor.submit(wait_for_prompt, source, dest, prompt_control)

            # Get user input
            try:
                raw = input(prompt, use_stderr=use_stderr) + "\n"
            except KeyboardInterrupt:
                process.send_signal(signal.SIGINT)
                continue
            except EOFError:
                break
            else:
                process.stdin.write(raw)

        # Close and wait process streams
        process.stdin.close()
        future.exception()

    # Wait process and return code
    return process.wait()


def wait_for_prompt(src, dest, prompt_control, buffersize=1):
    def read():
        value = src.read(buffersize)
        if value:
            return value
        raise EOFError

    def write(arg):
        if arg:
            dest.write(arg)
            dest.flush()

    # Prevent exception in macOS with large output (issue #42)
    if compat.platform == "darwin":
        fcntl.fcntl(dest.fileno(), fcntl.F_SETFL, 0)

    # Wait for first prompt control
    while True:
        current = read()
        if prompt_control in current:
            break
        write(current)

    preprompt, current = current.split(prompt_control, 1)
    write(preprompt)

    # Wait for second prompt control
    while prompt_control not in current:
        current += read()

    prompt, postprompt = current.split(prompt_control, 1)
    write(postprompt)

    return prompt


def input(prompt="", use_stderr=False):
    # Use readline if possible
    try:
        import readline  # noqa
    except ImportError:
        return builtins.input(prompt)
    # Use stdout
    if not use_stderr:
        return builtins.input(prompt)
    api = ctypes.pythonapi
    # Cross-platform compatibility
    if compat.platform == "darwin":
        stdin = "__stdinp"
        stderr = "__stderrp"
    else:
        stdin = "stdin"
        stderr = "stderr"
    # Get standard streams
    try:
        fin = ctypes.c_void_p.in_dll(api, stdin)
        ferr = ctypes.c_void_p.in_dll(api, stderr)
    # Cygwin fallback
    except ValueError:
        return builtins.input(prompt)
    # Call readline
    call_readline = api.PyOS_Readline
    call_readline.restype = ctypes.c_char_p
    result = call_readline(fin, ferr, prompt.encode())
    # Decode result
    if len(result) == 0:
        raise EOFError
    return result.decode().rstrip("\n")
