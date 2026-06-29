#!/usr/bin/env bash
# Provision (or tear down) a clean Hummingbot checkout + isolated conda env for an eval run.
#
# A clean room must NOT reuse the dev `hummingbot` env (make install hardcodes that name), so this
# creates a uniquely-named env from setup/environment.yml and replicates the install steps:
# conda develop, pip_packages, build_ext, and the `hbot` symlink.
#
# Usage:
#   setup_clean_env.sh [--branch <branch>] [--env <name>] [--workdir <dir>]
#   setup_clean_env.sh --teardown [--env <name>] [--workdir <dir>]
#
# Defaults: branch = current branch, env = hbot-eval-<rand>, workdir = a fresh mktemp dir.
# Prints `ENV=<name>` and `WORKDIR=<path>` on success — the AUT runs there with `conda activate <env>`.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/hummingbot/hummingbot.git}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # repo root (clone source for local branches)
BRANCH=""; ENV_NAME=""; WORKDIR=""; TEARDOWN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2;;
    --env) ENV_NAME="$2"; shift 2;;
    --workdir) WORKDIR="$2"; shift 2;;
    --teardown) TEARDOWN=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

command -v conda >/dev/null 2>&1 || { echo "conda not found in PATH" >&2; exit 1; }

if [[ "$TEARDOWN" == 1 ]]; then
  [[ -n "$ENV_NAME" ]] && conda env remove -n "$ENV_NAME" -y || true
  [[ -n "$WORKDIR" && -d "$WORKDIR" ]] && rm -rf "$WORKDIR" || true
  echo "torn down env='$ENV_NAME' workdir='$WORKDIR'"
  exit 0
fi

BRANCH="${BRANCH:-$(git -C "$SRC_DIR" rev-parse --abbrev-ref HEAD)}"
ENV_NAME="${ENV_NAME:-hbot-eval-$RANDOM}"
WORKDIR="${WORKDIR:-$(mktemp -d -t hbot-eval-XXXXXX)}/hummingbot"

echo ">> cloning $BRANCH into $WORKDIR" >&2
# Clone from the local repo so an unpushed eval branch works; falls back to the public URL.
if git -C "$SRC_DIR" rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  git clone --quiet --branch "$BRANCH" "$SRC_DIR" "$WORKDIR"
else
  git clone --quiet --branch "$BRANCH" "$REPO_URL" "$WORKDIR"
fi
cd "$WORKDIR"

echo ">> creating conda env '$ENV_NAME' from setup/environment.yml" >&2
# Override the hardcoded `name: hummingbot` so we don't touch the dev env.
sed "s/^name:.*/name: $ENV_NAME/" setup/environment.yml > /tmp/$ENV_NAME.yml
conda env create -n "$ENV_NAME" -f /tmp/$ENV_NAME.yml
rm -f /tmp/$ENV_NAME.yml

[[ "$(uname)" == "Darwin" ]] && conda install -n "$ENV_NAME" -y appnope >/dev/null 2>&1 || true

echo ">> installing package into '$ENV_NAME' (develop, pip_packages, build_ext)" >&2
conda run -n "$ENV_NAME" conda develop . >/dev/null
conda run -n "$ENV_NAME" python -m pip install --no-deps -r setup/pip_packages.txt >/dev/null
conda run -n "$ENV_NAME" --no-capture-output python setup.py build_ext --inplace >/dev/null
conda run -n "$ENV_NAME" bash -c 'ln -sf "'"$WORKDIR"'/bin/hbot" "$CONDA_PREFIX/bin/hbot"'

echo ">> verifying hbot" >&2
conda run -n "$ENV_NAME" hbot --version >/dev/null

echo "ENV=$ENV_NAME"
echo "WORKDIR=$WORKDIR"
echo ">> ready. AUT: cd $WORKDIR && conda activate $ENV_NAME && hbot --help" >&2
