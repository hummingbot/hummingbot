#!/usr/bin/env bash
set -euo pipefail

umask 077
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container_name="${STRATEGY_EVOLUTION_CONTAINER_NAME:-hummingbot-strategy-evolution}"
rollback_name="${container_name}-rollback"
action="${1:-status}"
host_python="${STRATEGY_EVOLUTION_PYTHON:-$(command -v python3 || true)}"

docker_bin="$(command -v docker || true)"
if [[ -z "$docker_bin" && -x /Applications/Docker.app/Contents/Resources/bin/docker ]]; then
  docker_bin=/Applications/Docker.app/Contents/Resources/bin/docker
fi
if [[ -z "$docker_bin" || -z "$host_python" || ! -x "$host_python" ]]; then
  echo "Docker and Python are required" >&2
  exit 2
fi

source_sha() {
  PYTHONPATH="$root" "$host_python" - "$root" <<'PY'
import sys
from pathlib import Path
from hummingbot.strategy_v2.evolution.operations import source_fingerprint
print(source_fingerprint(Path(sys.argv[1])))
PY
}

base_image() {
  "$host_python" - "$root/conf/strategy_evolution.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["policy"]["docker_image"])
PY
}

wait_for_liveness() {
  local name="$1" expected="$2" attempts="${STRATEGY_EVOLUTION_START_ATTEMPTS:-60}"
  for ((index=1; index<=attempts; index++)); do
    if "$docker_bin" exec "$name" /opt/conda/envs/hummingbot/bin/python \
      scripts/check_strategy_evolution_health.py \
      --mode liveness --require-live-process \
      --expected-source-sha256 "$expected" >/dev/null 2>&1; then
      return 0
    fi
    if [[ "$("$docker_bin" inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" != "true" ]]; then
      return 1
    fi
    sleep 5
  done
  return 1
}

build_image() {
  local sha="$1" base="$2" release="$3" image="$4"
  "$docker_bin" build \
    --file "$root/deploy/evolution/Dockerfile" \
    --build-arg "BASE_IMAGE=$base" \
    --build-arg "RELEASE_ID=$release" \
    --build-arg "SOURCE_SHA256=$sha" \
    --label "io.hummingbot.strategy-evolution.source-sha256=$sha" \
    --tag "$image" "$root"
}

create_container() {
  local sha="$1" release="$2" image="$3"
  local webhook_args=(-e STRATEGY_EVOLUTION_ALERT_WEBHOOK_URL)
  local backup_dir="${STRATEGY_EVOLUTION_BACKUP_DIR:-$root/../hummingbot-backups/strategy-evolution}"
  mkdir -p "$backup_dir"
  chmod 700 "$backup_dir"
  "$docker_bin" create \
    --name "$container_name" \
    --hostname strategy-evolution \
    --label hummingbot.strategy-evolution=true \
    --label "hummingbot.strategy-evolution.release=$release" \
    --label "hummingbot.strategy-evolution.source-sha256=$sha" \
    --restart unless-stopped \
    --stop-timeout 30 \
    --init \
    --user "$(id -u):$(id -g)" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,size=768m \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --pids-limit 256 \
    --memory "${STRATEGY_EVOLUTION_MEMORY:-4g}" \
    --cpus "${STRATEGY_EVOLUTION_CPUS:-2}" \
    --log-opt max-size=5m \
    --log-opt max-file=3 \
    -e HOME=/tmp/home \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e PYTHONPYCACHEPREFIX=/tmp/pycache \
    -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    -e 'PYTEST_ADDOPTS=-p no:cacheprovider' \
    -e PATH=/opt/conda/envs/hummingbot/bin:/opt/conda/bin:/usr/local/bin:/usr/bin:/bin \
    -e MPLCONFIGDIR=/tmp/matplotlib \
    -e PYTHONPATH=/home/hummingbot \
    -e STRATEGY_EVOLUTION_LOG_FILE=/home/hummingbot/data/strategy-evolution/logs/daemon.log \
    -e "STRATEGY_EVOLUTION_RELEASE_ID=$release" \
    -e "STRATEGY_EVOLUTION_SOURCE_SHA256=$sha" \
    -e "STRATEGY_EVOLUTION_IMAGE_REFERENCE=$image" \
    -e "STRATEGY_EVOLUTION_AUTO_START_PAPER=${STRATEGY_EVOLUTION_AUTO_START_PAPER:-0}" \
    -e "STRATEGY_EVOLUTION_INTERVAL=${STRATEGY_EVOLUTION_INTERVAL:-300}" \
    -e "STRATEGY_EVOLUTION_BACKUP_INTERVAL=${STRATEGY_EVOLUTION_BACKUP_INTERVAL:-21600}" \
    -e "STRATEGY_EVOLUTION_BACKUP_RETAIN=${STRATEGY_EVOLUTION_BACKUP_RETAIN:-14}" \
    "${webhook_args[@]}" \
    -v "$root/data:/home/hummingbot/data:rw" \
    -v "$root/reports:/home/hummingbot/reports:ro" \
    -v "$root/conf/controllers:/home/hummingbot/conf/controllers:rw" \
    -v "$root/conf/scripts:/home/hummingbot/conf/scripts:rw" \
    -v "$backup_dir:/backups:rw" \
    -w /home/hummingbot \
    --health-cmd "/opt/conda/envs/hummingbot/bin/python scripts/check_strategy_evolution_health.py --mode readiness --require-live-process --expected-source-sha256 $sha" \
    --health-interval 60s \
    --health-timeout 20s \
    --health-start-period 180s \
    --health-retries 3 \
    "$image" >/dev/null
}

install_container() {
  local sha base release image had_previous=0
  sha="$(source_sha)"
  base="$(base_image)"
  release="evo-${sha:0:12}"
  image="hummingbot-strategy-evolution:${sha:0:12}"
  build_image "$sha" "$base" "$release" "$image"
  "$host_python" "$root/scripts/strategy_evolution_backup.py" create >/dev/null

  "$docker_bin" rm -f "$rollback_name" >/dev/null 2>&1 || true
  if "$docker_bin" inspect "$container_name" >/dev/null 2>&1; then
    had_previous=1
    "$docker_bin" stop "$container_name" >/dev/null 2>&1 || true
    "$docker_bin" rename "$container_name" "$rollback_name"
  fi
  committed=0
  restore_previous_on_error() {
    if [[ "$committed" == 0 && "$had_previous" == 1 ]]; then
      "$docker_bin" rm -f "$container_name" >/dev/null 2>&1 || true
      if "$docker_bin" inspect "$rollback_name" >/dev/null 2>&1; then
        "$docker_bin" rename "$rollback_name" "$container_name" >/dev/null
        "$docker_bin" start "$container_name" >/dev/null
      fi
    fi
  }
  trap restore_previous_on_error ERR INT TERM
  if ! create_container "$sha" "$release" "$image"; then
    restore_previous_on_error
    committed=1
    trap - ERR INT TERM
    return 1
  fi
  "$docker_bin" start "$container_name" >/dev/null
  if ! wait_for_liveness "$container_name" "$sha"; then
    "$docker_bin" logs --tail 100 "$container_name" >&2 || true
    "$docker_bin" rm -f "$container_name" >/dev/null 2>&1 || true
    if [[ "$had_previous" == 1 ]]; then
      "$docker_bin" rename "$rollback_name" "$container_name"
      "$docker_bin" start "$container_name" >/dev/null
    fi
    committed=1
    trap - ERR INT TERM
    echo "deployment failed liveness; previous container restored" >&2
    return 1
  fi
  mkdir -p "$root/data/strategy-evolution"
  RELEASE="$release" IMAGE="$image" SOURCE_SHA="$sha" "$host_python" - "$root/data/strategy-evolution/deployment.json" <<'PY'
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
target = Path(sys.argv[1])
payload = {"version": 1, "deployed_at": datetime.now(timezone.utc).isoformat(), "release_id": os.environ["RELEASE"], "image": os.environ["IMAGE"], "source_sha256": os.environ["SOURCE_SHA"]}
temporary = target.with_suffix(".tmp")
temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
temporary.replace(target)
PY
  echo "deployed: $container_name release=$release image=$image"
  committed=1
  trap - ERR INT TERM
}

rollback_container() {
  if ! "$docker_bin" inspect "$rollback_name" >/dev/null 2>&1; then
    echo "no rollback container is available" >&2
    exit 1
  fi
  "$docker_bin" stop "$container_name" >/dev/null 2>&1 || true
  "$docker_bin" rm -f "$container_name" >/dev/null 2>&1 || true
  "$docker_bin" rename "$rollback_name" "$container_name"
  "$docker_bin" start "$container_name" >/dev/null
  echo "rolled back: $container_name"
}

case "$action" in
  install | restart) install_container ;;
  rollback) rollback_container ;;
  backup) "$host_python" "$root/scripts/strategy_evolution_backup.py" create ;;
  verify-backup)
    [[ -n "${2:-}" ]] || { echo "archive path required" >&2; exit 2; }
    "$host_python" "$root/scripts/strategy_evolution_backup.py" verify "$2"
    ;;
  stop) "$docker_bin" stop "$container_name" ;;
  uninstall)
    "$docker_bin" rm -f "$container_name" >/dev/null 2>&1 || true
    echo "uninstalled: $container_name"
    ;;
  status)
    "$docker_bin" inspect --format 'name={{.Name}} state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restarts={{.RestartCount}} release={{index .Config.Labels "hummingbot.strategy-evolution.release"}} source={{index .Config.Labels "hummingbot.strategy-evolution.source-sha256"}}' "$container_name"
    ;;
  logs) "$docker_bin" logs --tail "${STRATEGY_EVOLUTION_LOG_TAIL:-100}" "$container_name" ;;
  *) echo "usage: $0 {install|restart|rollback|backup|verify-backup|stop|uninstall|status|logs}" >&2; exit 2 ;;
esac
