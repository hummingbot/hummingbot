## Docker multi-bot quickstart (local + cloud)

### 1) Build an image with your local changes
```bash
chmod +x scripts/build_release_image.sh
./scripts/build_release_image.sh local/hummingbot v1
```

Rebuild when you change Python/Cython sources under `hummingbot/`, `controllers/`, `scripts/`, or any `.pyx` files. Bump the tag, e.g. `v1.0.1-local`.

### 2) Run a single bot (foreground or detached)
Foreground (shows the UI):
```bash
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1.0.0-local \
BOT_DIR="$(pwd)" \
docker-compose -f docker-compose.prod.yml up
```

Detached (background):
```bash
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1.0.0-local \
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
mkdir -p bots/DEURO-USDT/{conf,logs,data,certs}

mkdir -p bots/DEURO-BTC/{conf,logs,data,certs}

mkdir -p bots/DEPS-USDT/{conf,logs,data,certs}

mkdir -p bots/DEPS-BTC/{conf,logs,data,certs}
```

Start each bot with a unique project name (-p) and BOT_DIR:
```bash
# Bot 1
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/DEURO-USDT" \
docker-compose -f docker-compose.prod.yml -p DEURO-USDT up -d

# Bot 2
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/DEURO-BTC" \
docker-compose -f docker-compose.prod.yml -p DEURO-BTC up -d

IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/DEPS-USDT" \
docker-compose -f docker-compose.prod.yml -p DEPS-USDT up -d

# Bot 2
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1 \
BOT_DIR="$(pwd)/bots/DEPS-BTC" \
docker-compose -f docker-compose.prod.yml -p DEPS-BTC up -d
```

Logs / stop per bot:
```bash
BOT_DIR="$(pwd)/bots/hb001" docker-compose -f docker-compose.prod.yml -p hb001 logs -f
BOT_DIR="$(pwd)/bots/hb001" docker-compose -f docker-compose.prod.yml -p hb001 down         # keep data
BOT_DIR="$(pwd)/bots/hb001" docker-compose -f docker-compose.prod.yml -p hb001 down -v      # delete data
```

### 5) Upgrading to a new image tag
```bash
./scripts/build_release_image.sh local/hummingbot v1.0.1-local

# Restart each bot with the new tag
IMAGE_NAME=local/hummingbot IMAGE_TAG=v1.0.1-local \
BOT_DIR="$(pwd)/bots/hb001" \
docker-compose -f docker-compose.prod.yml -p hb001 up -d
```

### 6) Apple Silicon → linux/amd64 (optional)
If deploying to linux/amd64 from an ARM Mac, build a multi-arch image:
```bash
docker buildx create --use --name hb-builder || true
docker buildx build --platform linux/amd64 \
  -t local/hummingbot:v1.0.0-local \
  --load .
```
