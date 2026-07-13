#!/usr/bin/env bash
# Start the Binance paper PMM instance with the local source overrides that the
# operations console relies on. It never enables a live connector.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container_name="${HUMMINGBOT_CONTAINER_NAME:-hummingbot-pmm-mister-paper}"
image="${HUMMINGBOT_IMAGE:-hummingbot/hummingbot:latest}"
script_config="${SCRIPT_CONFIG:-conf_pmm_mister_paper.yml}"
network="${HUMMINGBOT_DOCKER_NETWORK:-host}"

# Docker Desktop on macOS keeps its CLI inside the application bundle until the
# user enables the optional PATH symlink. Resolve that location so the LAN
# runner works on a newly provisioned Mac without modifying system PATH.
docker_bin="${DOCKER_BIN:-}"
if [[ -z "$docker_bin" ]]; then
  docker_bin="$(command -v docker || true)"
fi
if [[ -z "$docker_bin" && -x /Applications/Docker.app/Contents/Resources/bin/docker ]]; then
  docker_bin=/Applications/Docker.app/Contents/Resources/bin/docker
fi
if [[ -z "$docker_bin" ]]; then
  echo "Docker CLI not found. Start Docker Desktop or set DOCKER_BIN." >&2
  exit 1
fi

# A non-interactive SSH deployment cannot access the macOS login keychain used
# by Docker Desktop's credential helper. An operator may point this at the
# isolated engine-local config to pull public images without altering their
# normal Docker login configuration.
if [[ -n "${HUMMINGBOT_DOCKER_CONFIG:-}" ]]; then
  export DOCKER_CONFIG="$HUMMINGBOT_DOCKER_CONFIG"
fi

: "${CONFIG_PASSWORD:?Set CONFIG_PASSWORD before starting the paper instance.}"

# Keep paper-trading costs aligned with the Binance account when a read-only
# USER_DATA key is supplied. Without it, the script writes the explicit
# 10 bps gross / 40% rebate / 6 bps net fallback instead of silently using a
# generic connector default. No order-capable key is required or passed on.
python3 "$root/scripts/sync_binance_fee_profile.py" --root "$root"

# Docker Desktop containers cannot reach a host-side proxy through 127.0.0.1.
# Operators can override this directly with HUMMINGBOT_CONTAINER_PROXY, or set
# HUMMINGBOT_DISABLE_PROXY=true when direct Binance connectivity is healthier.
if [[ "${HUMMINGBOT_DISABLE_PROXY:-false}" == "true" ]]; then
  proxy=""
else
  proxy="${HUMMINGBOT_CONTAINER_PROXY:-${HTTPS_PROXY:-${HTTP_PROXY:-${ALL_PROXY:-}}}}"
  proxy="${proxy//127.0.0.1/host.docker.internal}"
  proxy="${proxy//localhost/host.docker.internal}"
fi

"$docker_bin" rm -f "$container_name" >/dev/null 2>&1 || true

args=(
  run -dit
  --name "$container_name"
  --restart unless-stopped
  --network "$network"
  --env CONFIG_PASSWORD
  --env "SCRIPT_CONFIG=$script_config"
  --env "NO_PROXY=${NO_PROXY:-localhost,127.0.0.1,::1,.local}"
  --env "no_proxy=${no_proxy:-${NO_PROXY:-localhost,127.0.0.1,::1,.local}}"
  -v "$root/conf:/home/hummingbot/conf"
  -v "$root/logs:/home/hummingbot/logs"
  -v "$root/data:/home/hummingbot/data"
  -v "$root/certs:/home/hummingbot/certs"
  -v "$root/scripts:/home/hummingbot/scripts"
  -v "$root/controllers:/home/hummingbot/controllers"
  -v "$root/hummingbot/strategy_v2/routers:/home/hummingbot/hummingbot/strategy_v2/routers"
  -v "$root/hummingbot/strategy_v2/executors/executor_base.py:/home/hummingbot/hummingbot/strategy_v2/executors/executor_base.py"
  -v "$root/hummingbot/strategy_v2/executors/grid_executor/grid_executor.py:/home/hummingbot/hummingbot/strategy_v2/executors/grid_executor/grid_executor.py"
  -v "$root/hummingbot/strategy_v2/executors/order_executor/order_executor.py:/home/hummingbot/hummingbot/strategy_v2/executors/order_executor/order_executor.py"
  -v "$root/hummingbot/strategy_v2/executors/position_executor/position_executor.py:/home/hummingbot/hummingbot/strategy_v2/executors/position_executor/position_executor.py"
  -v "$root/hummingbot/core/web_assistant/connections/connections_factory.py:/home/hummingbot/hummingbot/core/web_assistant/connections/connections_factory.py"
  -v "$root/hummingbot/connector/exchange/binance/binance_constants.py:/home/hummingbot/hummingbot/connector/exchange/binance/binance_constants.py"
  -v "$root/hummingbot/connector/exchange/binance/binance_web_utils.py:/home/hummingbot/hummingbot/connector/exchange/binance/binance_web_utils.py"
)

if [[ -n "$proxy" ]]; then
  args+=(
    --env "HTTP_PROXY=$proxy"
    --env "HTTPS_PROXY=$proxy"
    --env "ALL_PROXY=$proxy"
    --env "http_proxy=$proxy"
    --env "https_proxy=$proxy"
    --env "all_proxy=$proxy"
  )
fi

args+=("$image" bash -lc 'conda activate hummingbot && ./bin/hummingbot_quickstart.py --v2 "$SCRIPT_CONFIG" -p "$CONFIG_PASSWORD"')
"$docker_bin" "${args[@]}"
