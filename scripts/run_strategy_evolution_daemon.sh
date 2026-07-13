#!/usr/bin/env bash
set -euo pipefail
umask 077

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
python_bin="${STRATEGY_EVOLUTION_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$python_bin" || ! -x "$python_bin" ]]; then
  echo "strategy evolution Python interpreter is unavailable: $python_bin" >&2
  exit 2
fi
"$python_bin" -c 'import pydantic, yaml' >/dev/null

mkdir -p "$root/data/strategy-evolution/logs"
export PYTHONUNBUFFERED=1
export STRATEGY_EVOLUTION_LOG_FILE="${STRATEGY_EVOLUTION_LOG_FILE:-$root/data/strategy-evolution/logs/daemon.log}"

args=(
  scripts/strategy_evolution_loop.py
  --run-checks
  --watch "${STRATEGY_EVOLUTION_INTERVAL:-300}"
  --max-iterations 0
  --initial-backoff "${STRATEGY_EVOLUTION_INITIAL_BACKOFF:-5}"
  --max-backoff "${STRATEGY_EVOLUTION_MAX_BACKOFF:-300}"
)
if [[ "${STRATEGY_EVOLUTION_AUTO_EXPERIMENT:-1}" == "1" ]]; then
  args+=(--auto-experiment)
fi

exec "$python_bin" "${args[@]}"
