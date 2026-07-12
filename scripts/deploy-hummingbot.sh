#!/usr/bin/env bash
# Hummingbot deployment helper.
# Mirrors the KKline deployment style: rsync to the shared cloud server, run
# Docker Compose under /opt, and let host Nginx own the public domain/SSL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.cloud.yml"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-$PROJECT_ROOT/.deploy.env}"

if [ -f "$DEPLOY_ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$DEPLOY_ENV_FILE"
    set +a
fi

CLOUD_SERVER_IP="${CLOUD_SERVER_IP:-47.254.246.53}"
CLOUD_SERVER_USER="${CLOUD_SERVER_USER:-root}"
CLOUD_SSH_PORT="${CLOUD_SSH_PORT:-2222}"
CLOUD_SSH_KEY="${CLOUD_SSH_KEY:-/Users/xinghailong/Documents/soft/KKline/deploy/LH.pem}"
CLOUD_PROJECT_PATH="${CLOUD_PROJECT_PATH:-/opt/hummingbot}"
CLOUD_DOMAIN="${CLOUD_DOMAIN:-humm.kline007.top}"
CLOUD_HEALTH_URL="${CLOUD_HEALTH_URL:-https://humm.kline007.top/health}"
CLOUD_CONTAINER="${CLOUD_CONTAINER:-hummingbot}"
CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-10}"
CLOUD_SSH_CMD_TIMEOUT="${CLOUD_SSH_CMD_TIMEOUT:-30}"
CLOUD_SSH_BUILD_TIMEOUT="${CLOUD_SSH_BUILD_TIMEOUT:-600}"
CLOUD_SSH_RETRY="${CLOUD_SSH_RETRY:-3}"
CLOUD_SSH_SOCKET="${CLOUD_SSH_SOCKET:-/tmp/hummingbot-ssh-control-$$}"
DEPLOY_LOCK="${DEPLOY_LOCK:-/tmp/server-deploy.lock}"
DEPLOY_LOCK_ACQUIRED=0

NC=$'\033[0m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
CYAN=$'\033[0;36m'

log() { printf '%s\n' "${CYAN}==>${NC} $*"; }
ok() { printf '%s\n' "${GREEN}OK${NC} $*"; }
warn() { printf '%s\n' "${YELLOW}WARN${NC} $*"; }
err() { printf '%s\n' "${RED}ERR${NC} $*" >&2; }

cloud_ssh_connect() {
    if [ -S "$CLOUD_SSH_SOCKET" ] && ssh -S "$CLOUD_SSH_SOCKET" -p "$CLOUD_SSH_PORT" -O check "$CLOUD_SERVER_USER@$CLOUD_SERVER_IP" 2>/dev/null; then
        return 0
    fi
    rm -f "$CLOUD_SSH_SOCKET"

    log "Opening SSH control connection..."
    local attempt=1
    while [ "$attempt" -le "$CLOUD_SSH_RETRY" ]; do
        if ssh -M -S "$CLOUD_SSH_SOCKET" -fN \
            -i "$CLOUD_SSH_KEY" \
            -p "$CLOUD_SSH_PORT" \
            -o StrictHostKeyChecking=no \
            -o BatchMode=yes \
            -o ConnectTimeout="$CLOUD_SSH_CONNECT_TIMEOUT" \
            -o ServerAliveInterval=30 \
            -o ServerAliveCountMax=10 \
            -o ControlPersist=10m \
            "$CLOUD_SERVER_USER@$CLOUD_SERVER_IP" 2>/dev/null; then
            ok "SSH control connection ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    warn "SSH control connection failed; falling back to normal SSH"
    return 1
}

cloud_ssh_disconnect() {
    if [ -S "$CLOUD_SSH_SOCKET" ]; then
        ssh -S "$CLOUD_SSH_SOCKET" -p "$CLOUD_SSH_PORT" -O exit "$CLOUD_SERVER_USER@$CLOUD_SERVER_IP" 2>/dev/null || true
        rm -f "$CLOUD_SSH_SOCKET"
    fi
}

cloud_ssh() {
    local alive_interval=5
    local alive_count=12
    if [ "${CLOUD_SSH_TIMEOUT:-$CLOUD_SSH_CMD_TIMEOUT}" -ge 60 ] 2>/dev/null; then
        alive_interval=30
        alive_count=20
    fi

    if [ -S "$CLOUD_SSH_SOCKET" ]; then
        ssh -S "$CLOUD_SSH_SOCKET" \
            -p "$CLOUD_SSH_PORT" \
            -o ServerAliveInterval="$alive_interval" \
            -o ServerAliveCountMax="$alive_count" \
            "$CLOUD_SERVER_USER@$CLOUD_SERVER_IP" "$@"
        return $?
    fi

    ssh -i "$CLOUD_SSH_KEY" \
        -p "$CLOUD_SSH_PORT" \
        -o StrictHostKeyChecking=no \
        -o BatchMode=yes \
        -o ConnectTimeout="$CLOUD_SSH_CONNECT_TIMEOUT" \
        -o ServerAliveInterval="$alive_interval" \
        -o ServerAliveCountMax="$alive_count" \
        "$CLOUD_SERVER_USER@$CLOUD_SERVER_IP" "$@"
}

cloud_ssh_script() {
    local payload
    payload="$(cat)"
    printf '%s' "$payload" | cloud_ssh bash -s
}

cleanup_on_exit() {
    release_deploy_lock 2>/dev/null || true
    cloud_ssh_disconnect
}
trap cleanup_on_exit EXIT

cloud_check_connection() {
    if [ ! -f "$CLOUD_SSH_KEY" ]; then
        err "SSH key not found: $CLOUD_SSH_KEY"
        return 1
    fi
    cloud_ssh_connect || true
    cloud_ssh "echo connected" >/dev/null
    ok "Cloud connection ready: $CLOUD_SERVER_IP"
}

acquire_deploy_lock() {
    if [ "$DEPLOY_LOCK_ACQUIRED" = "1" ]; then
        return 0
    fi
    log "Checking deploy lock..."
    if cloud_ssh "test -f '$DEPLOY_LOCK' && [ \$(( \$(date +%s) - \$(stat -c %Y '$DEPLOY_LOCK') )) -lt 600 ]" 2>/dev/null; then
        err "Deploy lock is busy: $(cloud_ssh "cat '$DEPLOY_LOCK' 2>/dev/null" || true)"
        return 1
    fi
    cloud_ssh "date '+Hummingbot %Y-%m-%d %H:%M:%S' > '$DEPLOY_LOCK'"
    DEPLOY_LOCK_ACQUIRED=1
    ok "Deploy lock acquired"
}

release_deploy_lock() {
    if [ "$DEPLOY_LOCK_ACQUIRED" = "1" ]; then
        cloud_ssh "rm -f '$DEPLOY_LOCK'" 2>/dev/null || true
        DEPLOY_LOCK_ACQUIRED=0
    fi
}

local_start() {
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" up -d
    ok "Local Hummingbot container started"
}

local_stop() {
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" down
    ok "Local Hummingbot container stopped"
}

local_status() {
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" ps
}

local_logs() {
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

cloud_sync() {
    log "Syncing project to cloud..."
    cloud_ssh "mkdir -p '$CLOUD_PROJECT_PATH'"

    rsync -az --delete \
        -e "ssh -i $CLOUD_SSH_KEY -p $CLOUD_SSH_PORT -o StrictHostKeyChecking=no" \
        --exclude '.git' \
        --exclude '.deploy.env' \
        --exclude '.env' \
        --exclude '.mypy_cache' \
        --exclude '.pytest_cache' \
        --exclude '.ruff_cache' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '*.so' \
        --exclude 'build/' \
        --exclude 'dist/' \
        --exclude 'logs/*' \
        --exclude 'data/*' \
        --exclude 'certs/*' \
        --exclude 'gateway-files/logs/*' \
        --exclude 'conf/connectors/*' \
        --exclude 'conf/strategies/*' \
        "$PROJECT_ROOT/" \
        "$CLOUD_SERVER_USER@$CLOUD_SERVER_IP:$CLOUD_PROJECT_PATH/"

    cloud_ssh "mkdir -p '$CLOUD_PROJECT_PATH/conf/connectors' '$CLOUD_PROJECT_PATH/conf/strategies' '$CLOUD_PROJECT_PATH/logs' '$CLOUD_PROJECT_PATH/data' '$CLOUD_PROJECT_PATH/certs' '$CLOUD_PROJECT_PATH/gateway-files/conf' '$CLOUD_PROJECT_PATH/gateway-files/logs'"
    ok "Sync complete"
}

cloud_write_env() {
    log "Writing remote compose env..."
    cloud_ssh "cd '$CLOUD_PROJECT_PATH' && cat > .env" <<EOF
COMPOSE_PROFILES=${COMPOSE_PROFILES:-}
CONFIG_PASSWORD=${CONFIG_PASSWORD:-}
CONFIG_FILE_NAME=${CONFIG_FILE_NAME:-}
SCRIPT_CONFIG=${SCRIPT_CONFIG:-}
HEADLESS_MODE=${HEADLESS_MODE:-false}
HUMMINGBOT_IMAGE=${HUMMINGBOT_IMAGE:-hummingbot/hummingbot:latest}
HUMMINGBOT_GATEWAY_IMAGE=${HUMMINGBOT_GATEWAY_IMAGE:-hummingbot/gateway:latest}
GATEWAY_PASSPHRASE=${GATEWAY_PASSPHRASE:-admin}
GATEWAY_DEV=${GATEWAY_DEV:-true}
EOF
    ok "Remote .env ready"
}

cloud_init() {
    log "Initializing cloud host..."
    cloud_check_connection
    acquire_deploy_lock
    cloud_sync
    cloud_write_env

    cloud_ssh_script <<REMOTE_SCRIPT
set -e
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null
if ! command -v nginx >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq nginx
fi
if ! command -v certbot >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx
fi
mkdir -p /var/www/html
cat > /etc/nginx/sites-available/hummingbot <<'NGINX_CONF'
server {
    listen 80;
    server_name ${CLOUD_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location = /health {
        default_type text/plain;
        return 200 "ok\n";
    }

    location / {
        return 404;
    }
}
NGINX_CONF
ln -sf /etc/nginx/sites-available/hummingbot /etc/nginx/sites-enabled/hummingbot
nginx -t
systemctl enable nginx >/dev/null 2>&1 || true
systemctl reload nginx || nginx -s reload
REMOTE_SCRIPT

    cloud_ssh_script <<REMOTE_SCRIPT
set -e
mkdir -p /etc/letsencrypt-hummingbot /var/lib/letsencrypt-hummingbot /var/log/letsencrypt-hummingbot
if [ ! -f /etc/letsencrypt-hummingbot/live/${CLOUD_DOMAIN}/fullchain.pem ]; then
    certbot certonly --webroot \
        -w /var/www/html \
        -d ${CLOUD_DOMAIN} \
        --email admin@kline007.top \
        --agree-tos \
        --no-eff-email \
        --non-interactive \
        --config-dir /etc/letsencrypt-hummingbot \
        --work-dir /var/lib/letsencrypt-hummingbot \
        --logs-dir /var/log/letsencrypt-hummingbot
fi
cat > /etc/nginx/sites-available/hummingbot <<'NGINX_CONF'
server {
    listen 80;
    server_name ${CLOUD_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${CLOUD_DOMAIN};

    ssl_certificate /etc/letsencrypt-hummingbot/live/${CLOUD_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt-hummingbot/live/${CLOUD_DOMAIN}/privkey.pem;

    location = /health {
        default_type text/plain;
        return 200 "ok\n";
    }

    location / {
        return 404;
    }
}
NGINX_CONF
cat > /etc/cron.d/certbot-hummingbot <<'CRON'
17 3 * * * root certbot renew --quiet --config-dir /etc/letsencrypt-hummingbot --work-dir /var/lib/letsencrypt-hummingbot --logs-dir /var/log/letsencrypt-hummingbot --deploy-hook "systemctl reload nginx"
CRON
chmod 644 /etc/cron.d/certbot-hummingbot
nginx -t
systemctl reload nginx || nginx -s reload
REMOTE_SCRIPT

    CLOUD_SSH_TIMEOUT="$CLOUD_SSH_BUILD_TIMEOUT" cloud_ssh "cd '$CLOUD_PROJECT_PATH' && docker compose -f docker-compose.cloud.yml up -d"
    release_deploy_lock
    ok "Cloud init complete: https://$CLOUD_DOMAIN"
}

cloud_deploy() {
    log "Deploying Hummingbot to cloud..."
    cloud_check_connection
    acquire_deploy_lock
    cloud_sync
    cloud_write_env
    CLOUD_SSH_TIMEOUT="$CLOUD_SSH_BUILD_TIMEOUT" cloud_ssh "cd '$CLOUD_PROJECT_PATH' && docker compose -f docker-compose.cloud.yml up -d"
    cloud_ssh "systemctl reload nginx >/dev/null 2>&1 || nginx -s reload >/dev/null 2>&1 || true"
    release_deploy_lock
    ok "Deploy complete: https://$CLOUD_DOMAIN"
}

cloud_restart() {
    cloud_check_connection
    cloud_ssh "cd '$CLOUD_PROJECT_PATH' && docker compose -f docker-compose.cloud.yml restart"
    ok "Cloud container restarted"
}

cloud_down() {
    cloud_check_connection
    cloud_ssh "cd '$CLOUD_PROJECT_PATH' && docker compose -f docker-compose.cloud.yml down"
    ok "Cloud container stopped"
}

cloud_status() {
    cloud_check_connection
    cloud_ssh_script <<REMOTE_SCRIPT
set +e
echo "== Compose =="
cd "$CLOUD_PROJECT_PATH" && docker compose -f docker-compose.cloud.yml ps
echo
echo "== Container =="
docker ps --filter name="$CLOUD_CONTAINER" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo
echo "== Domain =="
echo "-- local HTTP --"
curl -sS -i --max-time 5 "http://127.0.0.1/health" -H "Host: $CLOUD_DOMAIN" 2>&1 | head -8
echo
echo "-- public HTTPS --"
curl -sS -i --max-time 5 "$CLOUD_HEALTH_URL" 2>&1 | head -8
echo
echo "== Disk =="
df -h / | tail -1
REMOTE_SCRIPT
}

cloud_logs() {
    cloud_check_connection
    cloud_ssh "docker logs -f --tail=100 '$CLOUD_CONTAINER'"
}

cloud_attach() {
    cloud_check_connection
    cloud_ssh "docker attach '$CLOUD_CONTAINER'"
}

usage() {
    cat <<EOF
Usage: $0 <command>

Local:
  start       Start local container with docker-compose.cloud.yml
  stop        Stop local container
  status      Show local compose status
  logs        Follow local logs

Cloud:
  init        First-time setup: sync, install Docker/Nginx/Certbot, start service
  deploy|c    Sync code and start/update container
  restart     Restart cloud container
  down        Stop cloud compose stack
  cs          Show cloud status
  cl          Follow cloud logs
  attach      Attach to Hummingbot CLI on cloud

Target:
  $CLOUD_SERVER_USER@$CLOUD_SERVER_IP:$CLOUD_SSH_PORT
  $CLOUD_PROJECT_PATH
  https://$CLOUD_DOMAIN
EOF
}

case "${1:-}" in
    start) local_start ;;
    stop) local_stop ;;
    status) local_status ;;
    logs) local_logs ;;
    init) cloud_init ;;
    deploy|c) cloud_deploy ;;
    restart) cloud_restart ;;
    down) cloud_down ;;
    cs|cloud-status) cloud_status ;;
    cl|cloud-logs) cloud_logs ;;
    attach) cloud_attach ;;
    help|-h|--help|"") usage ;;
    *) err "Unknown command: $1"; usage; exit 1 ;;
esac
