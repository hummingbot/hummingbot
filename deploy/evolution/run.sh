#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /tmp/home /tmp/matplotlib

backup_loop() {
  while true; do
    /opt/conda/envs/hummingbot/bin/python scripts/strategy_evolution_backup.py create \
      --root /home/hummingbot --backup-dir /backups \
      --retain "${STRATEGY_EVOLUTION_BACKUP_RETAIN:-14}" || true
    sleep "${STRATEGY_EVOLUTION_BACKUP_INTERVAL:-21600}"
  done
}
backup_loop &

/opt/conda/envs/hummingbot/bin/python - <<'PY'
import json
import os
from pathlib import Path

source = Path("conf/strategy_evolution.json")
target = Path("/tmp/strategy_evolution.json")
payload = json.loads(source.read_text(encoding="utf-8"))
payload["policy"]["experiment_runtime"] = "host"
payload["policy"]["auto_start_paper_candidates"] = (
    os.environ.get("STRATEGY_EVOLUTION_AUTO_START_PAPER", "0") == "1"
)
payload["policy"]["allow_live_actions"] = False
target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

exec /opt/conda/envs/hummingbot/bin/python scripts/strategy_evolution_loop.py \
  --config /tmp/strategy_evolution.json \
  --run-checks \
  --auto-experiment \
  --watch "${STRATEGY_EVOLUTION_INTERVAL:-300}" \
  --max-iterations 0 \
  --initial-backoff "${STRATEGY_EVOLUTION_INITIAL_BACKOFF:-5}" \
  --max-backoff "${STRATEGY_EVOLUTION_MAX_BACKOFF:-300}"
