## Docker multi-bot quickstart (local + cloud)

### 1) Build an image with your local changes
```bash
chmod +x scripts/build_release_image.sh
./scripts/build_release_image.sh local/hummingbot v1
```

Rebuild when you change Python/Cython sources under `hummingbot/`, `controllers/`, `scripts/`, or any `.pyx` files. Bump the tag, e.g. `v1`.

### 2) Run a single bot (foreground or detached)
Foreground (shows the UI):
```bash
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)" \
docker-compose -f docker-compose.prod.yml up
```

Detached (background):
```bash
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)" \
docker-compose -f docker-compose.prod.yml up -d
```

Attach/detach:
```bash
docker attach <container_id_or_name>   # detach: Ctrl-p then Ctrl-q
```

### 3) Persistence (on your host)
- Configs: `${BOT_DIR}/conf` (encrypted API keys, strategies, connector settings)
- Logs: `${BOT_DIR}/logs` (errors also in `errors.log`)
- Data: `${BOT_DIR}/data`
- Certs: `${BOT_DIR}/certs`

### 4) Run multiple independent bots
Create per-bot folders (first time only):
```bash
mkdir -p bots/deuro-usdt/{conf,logs,data,certs}

mkdir -p bots/deuro-btc/{conf,logs,data,certs}

mkdir -p bots/deps-usdt/{conf,logs,data,certs}

mkdir -p bots/deps-btc/{conf,logs,data,certs}
```

Start each bot with a unique project name (-p) and BOT_DIR:
```bash
# Bot 1
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/deuro-usdt" \
docker-compose -f docker-compose.prod.yml -p deuro-usdt up -d

# Bot 2
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/deuro-btc" \
docker-compose -f docker-compose.prod.yml -p deuro-btc up -d

IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/deps-usdt" \
docker-compose -f docker-compose.prod.yml -p deps-usdt up -d

# Bot 2
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/deps-btc" \
docker-compose -f docker-compose.prod.yml -p deps-btc up -d
```

Logs / stop per bot:
```bash
BOT_DIR="$(pwd)/bots/deuro-usdt" docker-compose -f docker-compose.prod.yml -p deuro-usdt logs -f
BOT_DIR="$(pwd)/bots/deuro-usdt" docker-compose -f docker-compose.prod.yml -p deuro-usdt down         # keep data
BOT_DIR="$(pwd)/bots/deuro-usdt" docker-compose -f docker-compose.prod.yml -p deuro-usdt down -v      # delete data
```

### 5) Upgrading to a new image tag
```bash
./scripts/build_release_image.sh local/hummingbot v1

# Restart each bot with the new tag
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/deuro-usdt" \
docker-compose -f docker-compose.prod.yml -p deuro-usdt up -d
```

### 6) Apple Silicon → linux/amd64 (optional)
If deploying to linux/amd64 from an ARM Mac, build a multi-arch image:
```bash
docker buildx create --use --name hb-builder || true
docker buildx build --platform linux/amd64 \
  -t local/hummingbot:v1 \
  --load .
```
