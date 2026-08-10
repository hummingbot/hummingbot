"""``hbot update`` — update a source install to the latest code on its branch.

Update means *the software*, per install type:

* **source checkout** — ``git fetch`` + fast-forward to the branch's upstream, then rebuild
  the Cython extensions if any compiled sources changed. Never crosses branches, never
  merges: a diverged local branch fails with instructions instead of guessing.
* **Docker** — a container cannot replace its own image; the command fails fast with the
  exact host-side commands (``docker compose pull && docker compose up -d``).
"""
import os
import subprocess
import sys
from pathlib import Path

import typer

from kairos.cli.output import ExitCode, echo, emit, fail, json_option, render_kv

REPO_ROOT = Path(__file__).resolve().parents[3]

GIT_TIMEOUT = 120  # network fetch ceiling; the build step runs untimed (it legitimately takes minutes)

# Changes to these require recompiling the extensions for the running install to match the code.
COMPILED_SOURCES = ("*.pyx", "*.pxd", "setup.py")


def _git(*args: str) -> str:
    """Run one git command in the repo root; fail the command with git's stderr on error."""
    try:
        proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                              text=True, timeout=GIT_TIMEOUT)
    except FileNotFoundError:
        fail("git is not installed — `hbot update` needs it on a source install", ExitCode.ERROR)
    except subprocess.TimeoutExpired:
        fail(f"git {' '.join(args)} timed out after {GIT_TIMEOUT}s", ExitCode.TIMEOUT)
    if proc.returncode != 0:
        fail(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}",
             ExitCode.ERROR)
    return proc.stdout.strip()


def _version() -> str:
    try:
        return (REPO_ROOT / "kairos" / "VERSION").read_text().strip()
    except OSError:
        return "unknown"


def _rebuild_extensions() -> None:
    """Recompile in place, streaming output (this is the slow, visible part of an update)."""
    echo("rebuilding Cython extensions (this takes a few minutes)...")
    proc = subprocess.run([sys.executable, "setup.py", "build_ext", "--inplace", "-j", "8"],
                          cwd=REPO_ROOT)
    if proc.returncode != 0:
        fail("extension build failed — the checkout is updated but NOT rebuilt; "
             "fix the build (see output above) or run `make install`", ExitCode.ERROR)


def update(
    check: bool = typer.Option(False, "--check", help="Only report whether an update is available."),
    as_json: bool = json_option(),
) -> None:
    """Update hbot to the latest version of its branch (source installs)."""
    if os.environ.get("INSTALLATION_TYPE") == "docker":
        fail("this is a Docker install — a container cannot replace its own image. "
             "Update from the HOST:  docker compose pull && docker compose up -d",
             ExitCode.ERROR)

    from kairos.cli import bot
    if bot.running():
        fail("a bot is running — `hbot stop` before updating", ExitCode.ERROR)

    if not (REPO_ROOT / ".git").exists():
        fail(f"{REPO_ROOT} is not a git checkout — `hbot update` only knows how to update "
             f"a source install (Docker: docker compose pull && docker compose up -d)",
             ExitCode.ERROR)

    _git("fetch", "--quiet")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    local = _git("rev-parse", "--short", "HEAD")
    # A branch with no upstream has no "latest" to compare against — say so, don't guess one.
    remote = _git("rev-parse", "--short", "@{u}")
    behind = int(_git("rev-list", "--count", "HEAD..@{u}"))
    ahead = int(_git("rev-list", "--count", "@{u}..HEAD"))

    if check or behind == 0:
        record = {"version": _version(), "branch": branch, "current": local, "latest": remote,
                  "behind": behind, "ahead": ahead, "up_to_date": behind == 0}
        emit(record, render_kv(record, title="update --check" if check else "update"), as_json)
        return

    if ahead > 0:
        fail(f"local branch has {ahead} commit(s) the upstream lacks — refusing to guess; "
             f"update manually (e.g. `git pull --rebase`) and rerun", ExitCode.ERROR)

    old_version = _version()
    _git("merge", "--ff-only", "@{u}")

    changed = _git("diff", "--name-only", f"{local}..HEAD", "--", *COMPILED_SOURCES)
    rebuilt = bool(changed)
    if rebuilt:
        _rebuild_extensions()

    env_changed = _git("diff", "--name-only", f"{local}..HEAD", "--", "setup/environment.yml")
    record: dict = {"version": f"{old_version} -> {_version()}", "branch": branch,
                    "updated": f"{local} -> {_git('rev-parse', '--short', 'HEAD')}",
                    "commits": behind, "extensions_rebuilt": rebuilt}
    if env_changed:
        record["note"] = "setup/environment.yml changed — run `make install` to update the conda env"
    emit(record, render_kv(record, title="update"), as_json)
