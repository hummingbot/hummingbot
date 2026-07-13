#!/usr/bin/env bash
set -euo pipefail

label="com.hummingbot.strategy-evolution"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="$root/deploy/launchd/$label.plist.example"
target="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"
action="${1:-status}"

python_bin="${STRATEGY_EVOLUTION_PYTHON:-$(command -v python3 || true)}"

render_plist() {
  if [[ "$root" == "$HOME/Documents/"* ]]; then
    echo "launchd cannot access this macOS Documents workspace; use manage_strategy_evolution_container.sh" >&2
    exit 2
  fi
  if [[ -z "$python_bin" || ! -x "$python_bin" ]]; then
    echo "Python interpreter is unavailable: $python_bin" >&2
    exit 2
  fi
  "$python_bin" -c 'import pydantic, yaml' >/dev/null
  mkdir -p "$HOME/Library/LaunchAgents" "$root/data/strategy-evolution/logs"
  ROOT="$root" PYTHON_BIN="$python_bin" TEMPLATE="$template" TARGET="$target" \
    "$python_bin" - <<'PY'
import os
from pathlib import Path

template = Path(os.environ["TEMPLATE"]).read_text(encoding="utf-8")
rendered = template.replace("__ROOT__", os.environ["ROOT"]).replace(
    "__PYTHON__", os.environ["PYTHON_BIN"]
)
target = Path(os.environ["TARGET"])
temporary = target.with_suffix(".plist.tmp")
temporary.write_text(rendered, encoding="utf-8")
temporary.replace(target)
PY
  plutil -lint "$target" >/dev/null
}

case "$action" in
  install)
    render_plist
    launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
    launchctl bootstrap "$domain" "$target"
    launchctl enable "$domain/$label"
    launchctl kickstart -k "$domain/$label"
    echo "installed: $target"
    ;;
  uninstall)
    launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
    rm -f "$target"
    echo "uninstalled: $label"
    ;;
  restart)
    render_plist
    launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
    launchctl bootstrap "$domain" "$target"
    launchctl kickstart -k "$domain/$label"
    echo "restarted: $label"
    ;;
  status)
    launchctl print "$domain/$label"
    ;;
  *)
    echo "usage: $0 {install|uninstall|restart|status}" >&2
    exit 2
    ;;
esac
