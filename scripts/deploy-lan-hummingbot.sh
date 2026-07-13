#!/usr/bin/env bash
# Deploy the Hummingbot execution engine to the designated LAN Mac. This is a
# paper-only preparation: it starts the loopback-bound admin console and syncs
# no credentials, encrypted configuration, ledger, logs, or private keys.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-$PROJECT_ROOT/.deploy.lan.env}"

if [[ -f "$DEPLOY_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$DEPLOY_ENV_FILE"
  set +a
fi

LAN_SERVER_HOST="${LAN_SERVER_HOST:-192.168.102.7}"
LAN_SERVER_USER="${LAN_SERVER_USER:-allenxing00}"
LAN_SSH_PORT="${LAN_SSH_PORT:-22}"
LAN_SSH_KEY="${LAN_SSH_KEY:-}"
LAN_CONTROL_PLANE_PATH="${LAN_CONTROL_PLANE_PATH:-/Users/$LAN_SERVER_USER/Documents/soft/hummingbot}"
LAN_ENGINE_PATH="${LAN_ENGINE_PATH:-/Users/$LAN_SERVER_USER/Documents/soft/hummingbot-engine}"
LAN_DOCKER_BIN="${LAN_DOCKER_BIN:-/Applications/Docker.app/Contents/Resources/bin/docker}"
LAN_DOCKER_CONFIG="${LAN_DOCKER_CONFIG:-$LAN_ENGINE_PATH/.docker}"
LAN_BUILDX_CONFIG="${LAN_BUILDX_CONFIG:-$LAN_ENGINE_PATH/.buildx}"
LAN_ADMIN_BIND_HOST="${LAN_ADMIN_BIND_HOST:-127.0.0.1}"
LAN_ADMIN_PORT="${LAN_ADMIN_PORT:-3217}"
REMOTE_TARGET="$LAN_SERVER_USER@$LAN_SERVER_HOST"

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ -n "$LAN_ENGINE_PATH" && "$LAN_ENGINE_PATH" != "/" ]] || die "LAN_ENGINE_PATH must be a dedicated non-root directory"
[[ "$LAN_ENGINE_PATH" != "$LAN_CONTROL_PLANE_PATH" ]] || die "LAN_ENGINE_PATH must not overwrite LAN_CONTROL_PLANE_PATH"

ssh_options=(
  -p "$LAN_SSH_PORT"
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=4
)
if [[ -n "$LAN_SSH_KEY" ]]; then
  [[ -f "$LAN_SSH_KEY" ]] || die "LAN_SSH_KEY does not exist: $LAN_SSH_KEY"
  ssh_options+=(-i "$LAN_SSH_KEY")
fi

remote() {
  ssh "${ssh_options[@]}" "$REMOTE_TARGET" "export PATH='/Applications/Docker.app/Contents/Resources/bin':\"\$PATH\"; $*"
}

preflight() {
  log "Checking SSH, Docker Desktop, and isolated target path"
  remote "test -x '$LAN_DOCKER_BIN'; '$LAN_DOCKER_BIN' version --format '{{.Server.Version}}'; '$LAN_DOCKER_BIN' compose version; test '$LAN_ENGINE_PATH' != '$LAN_CONTROL_PLANE_PATH'"
  log "Remote target: $REMOTE_TARGET:$LAN_ENGINE_PATH"
}

prepare_docker_config() {
  # Keep the Compose and Buildx plugins discoverable while avoiding the remote
  # user's Docker config, whose credential helper requires an unlocked macOS
  # login keychain during non-interactive SSH sessions.
  remote "base='$LAN_DOCKER_CONFIG'; mkdir -p \"\$base/cli-plugins\"; printf '{}\\n' > \"\$base/config.json\"; for plugin in docker-compose docker-buildx; do if [ -x \"\$HOME/.docker/cli-plugins/\$plugin\" ]; then ln -sfn \"\$HOME/.docker/cli-plugins/\$plugin\" \"\$base/cli-plugins/\$plugin\"; fi; done; DOCKER_CONFIG=\"\$base\" '$LAN_DOCKER_BIN' compose version >/dev/null; DOCKER_CONFIG=\"\$base\" '$LAN_DOCKER_BIN' buildx version >/dev/null"
}

sync_engine() {
  log "Syncing execution-engine source without secrets or runtime history"
  remote "mkdir -p '$LAN_ENGINE_PATH/conf/connectors' '$LAN_ENGINE_PATH/conf/strategies' '$LAN_ENGINE_PATH/logs' '$LAN_ENGINE_PATH/data' '$LAN_ENGINE_PATH/certs'"

  local rsync_ssh="ssh -p $LAN_SSH_PORT -o BatchMode=yes -o ConnectTimeout=10"
  if [[ -n "$LAN_SSH_KEY" ]]; then
    rsync_ssh+=" -i $LAN_SSH_KEY"
  fi
  rsync -az \
    -e "$rsync_ssh" \
    --exclude '.git' \
    --exclude '.codex' \
    --exclude '.deploy.env' \
    --exclude '.deploy.lan.env' \
    --exclude '.env' \
    --exclude '.mypy_cache' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude '__pycache__' \
    --exclude 'node_modules' \
    --exclude '.next' \
    --exclude 'build' \
    --exclude 'dist' \
    --exclude 'logs/***' \
    --exclude 'data/***' \
    --exclude 'certs/***' \
    --exclude 'conf/connectors/***' \
    --exclude 'conf/strategies/***' \
    "$PROJECT_ROOT/" "$REMOTE_TARGET:$LAN_ENGINE_PATH/"
  remote "mkdir -p '$LAN_ENGINE_PATH/conf/connectors' '$LAN_ENGINE_PATH/conf/strategies' '$LAN_ENGINE_PATH/logs' '$LAN_ENGINE_PATH/data' '$LAN_ENGINE_PATH/certs'"
}

start_admin() {
  log "Building and starting the LAN admin console on $LAN_ADMIN_BIND_HOST:$LAN_ADMIN_PORT"
  # Use an engine-local Docker config. The remote Mac's default config points
  # at the interactive macOS keychain, which is unavailable over batch SSH.
  remote "mkdir -p '$LAN_DOCKER_CONFIG' '$LAN_BUILDX_CONFIG' && cd '$LAN_ENGINE_PATH' && DOCKER_CONFIG='$LAN_DOCKER_CONFIG' BUILDX_CONFIG='$LAN_BUILDX_CONFIG' ADMIN_BIND_HOST='$LAN_ADMIN_BIND_HOST' ADMIN_PORT='$LAN_ADMIN_PORT' '$LAN_DOCKER_BIN' compose -f docker-compose.lan.yml up -d --build admin"
  remote "'$LAN_DOCKER_BIN' inspect --format '{{.State.Status}}' hummingbot-ai-admin"
  log "Admin is available at http://$LAN_ADMIN_BIND_HOST:$LAN_ADMIN_PORT/admin"
}

start_evolution() {
  log "Building and transactionally starting the Strategy Evolution Loop"
  remote "cd '$LAN_ENGINE_PATH' && DOCKER_CONFIG='$LAN_DOCKER_CONFIG' BUILDX_CONFIG='$LAN_BUILDX_CONFIG' scripts/manage_strategy_evolution_container.sh install"
  remote "'$LAN_DOCKER_BIN' exec hummingbot-strategy-evolution /opt/conda/envs/hummingbot/bin/python scripts/check_strategy_evolution_health.py --mode liveness --require-live-process"
}

status() {
  preflight
  prepare_docker_config
  remote "cd '$LAN_ENGINE_PATH' && DOCKER_CONFIG='$LAN_DOCKER_CONFIG' '$LAN_DOCKER_BIN' compose -f docker-compose.lan.yml ps; '$LAN_DOCKER_BIN' ps --filter name=hummingbot-pmm-mister-paper --format 'paper={{.Names}} {{.Status}}'; if '$LAN_DOCKER_BIN' inspect hummingbot-strategy-evolution >/dev/null 2>&1; then scripts/manage_strategy_evolution_container.sh status; else echo 'strategy-evolution: not installed'; fi"
}

usage() {
  cat <<EOF
Usage: $0 <prepare|deploy|status>

  prepare   Check remote prerequisites and sync the isolated engine directory.
  deploy    Prepare, then start the admin console and Strategy Evolution Loop.
  status    Show remote admin and paper-container status.

Target: $REMOTE_TARGET:$LAN_ENGINE_PATH
EOF
}

case "${1:-}" in
  prepare) preflight; prepare_docker_config; sync_engine ;;
  deploy) preflight; prepare_docker_config; sync_engine; start_admin; start_evolution ;;
  status) status ;;
  help|-h|--help|"") usage ;;
  *) die "Unknown command: $1" ;;
esac
