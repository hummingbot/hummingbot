#!/usr/bin/env python
"""Manual smoke harness: drive one full ``hbot`` CLI lifecycle for a strategy and print a JSON report.

For each strategy it runs: strategy create -> set/patch required fields -> start -> wait-ready ->
status -> logs -> update -> history -> trades -> stop. Heuristically fills required fields and swaps
binance/real trading connectors to gate_io paper trade (candles stay real). NOT a unit test (it spawns
real detached bots and may touch live venues); run manually.

Env:
  HBOT_PASSWORD  (required) keystore password used by hbot
  HBOT_PYTHON    (optional) python interpreter for the hbot env (default: current)
  HBOT_REPO      (optional) repo root for conf dirs (default: cwd)

Usage:
  HBOT_PASSWORD=... python test/hummingbot/cli/strategy_lifecycle_smoke.py <v1|v2|controller> <strategy> <instance> [key=val ...]
"""
import json
import os
import subprocess
import sys
import time

PY = os.environ.get("HBOT_PYTHON", sys.executable)
BASE = [PY, "-m", "hummingbot.cli.main"]
if not os.environ.get("HBOT_PASSWORD"):
    sys.exit("set HBOT_PASSWORD env var (the keystore password) before running")
EXCH = "gate_io_paper_trade"   # gate_io works here (binance is geo-blocked); paper => no real funds


def cli(*args, timeout=180):
    try:
        r = subprocess.run([*BASE, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"_timeout": True, "_rc": -1}
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except Exception:
        return {"_raw": (out + "\n" + r.stderr)[-1500:], "_rc": r.returncode}


def heuristic(field):
    f = field.lower()
    is_pair = "trading_pair" in f or f == "market" or "pair" in f
    is_venue = (("market" in f) or ("exchange" in f) or ("connector" in f)) and not is_pair
    if is_pair:
        return "BTC-USDT"
    if is_venue:
        return "kucoin_paper_trade" if "taker" in f else EXCH
    if "spread" in f:
        return "0.5"
    if "leverage" in f:
        return "1"
    if "profitab" in f:
        return "0.5"
    if "amount" in f or "size" in f or "notional" in f:
        return "20"
    if "time" in f or "refresh" in f or "interval" in f:
        return "30"
    if "pct" in f or "percent" in f or "ratio" in f or "allocation" in f:
        return "0.5"
    if "price" in f:
        return "60000"
    return "1"


CONF_DIRS = {"v1-strategy": "conf/strategies", "v2-script": "conf/scripts", "controller": "conf/controllers"}
ROOT = os.environ.get("HBOT_REPO", os.getcwd())
UPDATE_CANDIDATES = ["order_amount", "bid_spread", "spread", "total_amount_quote", "order_refresh_time",
                     "amount", "leverage", "min_profitability"]


def conf_path(stype, fname):
    return os.path.join(ROOT, CONF_DIRS[stype], fname)


def patch_config(stype, fname):
    """Swap binance connectors to gate_io paper (binance is geo-blocked) and pick an update key.

    Returns the chosen update key (a numeric field present in the config), or None.
    """
    import re
    p = conf_path(stype, fname)
    if not os.path.exists(p):
        return None
    lines = open(p).read().splitlines()
    out, keys = [], {}
    pair = "BTC-USDT"
    for ln in lines:
        m = re.match(r"([a-zA-Z0-9_]+):\s*(.*)", ln)
        if m:
            k, v = m.group(1), m.group(2).strip().strip("'\"")
            keys[k] = v
            if k == "trading_pair" and v:
                pair = v
            if "candles" in k and ("connector" in k):
                # candles need a REAL market-data connector (paper has no candles); use gate_io
                ln = f"{k}: gate_io"
            elif "candles" in k and ("pair" in k or k.endswith("trading_pair")):
                ln = f"{k}: {pair}"
            elif k == "interval" and v not in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
                ln = f"{k}: 5m"   # gate_io candles support a fixed interval set; 3m etc. are rejected
            elif (("connector" in k or "exchange" in k) and v and v not in ("null", "[]")
                  and not v.endswith("_paper_trade")):
                # any real trading connector -> paper (avoids "API keys required")
                repl = "kucoin_paper_trade" if "taker" in k else "gate_io_paper_trade"
                ln = f"{k}: {repl}"
        out.append(ln)
    open(p, "w").write("\n".join(out) + "\n")
    for c in UPDATE_CANDIDATES:
        if c in keys:
            return c
    return None


def status(instance):
    return cli("status", instance, "--json", timeout=60)


def wait_ready(instance, secs=70):
    deadline = time.time() + secs
    last = {}
    while time.time() < deadline:
        s = status(instance)
        last = s
        fs = s.get("format_status", "") or ""
        eng = s.get("engine", {}) or {}
        conns = eng.get("connectors", {}) or {}
        ready = any(c.get("ready") for c in conns.values()) if conns else False
        if fs and "not ready" not in fs and ("Orders" in fs or "Market" in fs or ready):
            return s, True
        time.sleep(4)
    return last, False


def main():
    stype, strategy, instance, *overrides = sys.argv[1:]
    flag = {"v1-strategy": "--v1-strategy", "v2-script": "--v2-script", "controller": "--controller"}[stype]
    fname = f"conf_clitest_{instance}.yml"
    ov = dict(kv.split("=", 1) for kv in overrides)
    R = {"strategy": strategy, "type": stype}

    # make idempotent: remove any prior config of this name from all conf dirs
    for d in ("conf/strategies", "conf/scripts", "conf/controllers"):
        p = os.path.join("/Users/feng/hummingbot", d, fname)
        if os.path.exists(p):
            os.remove(p)

    c = cli("strategy", "create", flag, strategy, "--name", fname, "--json")
    if not c.get("ok"):
        R["create"] = f"FAIL: {c.get('error') or c.get('_raw', '')[:300]}"
        print(json.dumps(R, indent=2)); return
    req = c.get("required_fields", []) or []
    R["required"] = req

    setfails = []
    update_key = None
    for f in req:
        val = ov.get(f, heuristic(f))
        s = cli("strategy", "set", fname, f, val, "--json")
        if not s.get("ok"):
            setfails.append(f"{f}={val}:{(s.get('error') or s.get('_raw', '') or '')[:100]}")
        if update_key is None and ("amount" in f.lower() or "spread" in f.lower()):
            update_key = f
    # also apply pure overrides that aren't required fields
    for k, v in ov.items():
        if k not in req:
            cli("strategy", "set", fname, k, v, "--json")
    R["sets"] = "ok" if not setfails else f"FAIL: {setfails}"

    # swap binance->gate_io paper in the written config; pick an update key from config if none yet
    cfg_update_key = patch_config(stype, fname)
    if update_key is None:
        update_key = cfg_update_key

    st = cli("start", flag, fname, "--name", instance, "--json", timeout=120)
    if not st.get("ok"):
        R["start"] = f"FAIL: {st.get('error') or st.get('_raw', '')[:400]}"
        print(json.dumps(R, indent=2)); return
    R["start"] = "ok"

    s, ready = wait_ready(instance)
    eng = s.get("engine", {}) or {}
    fs = s.get("format_status", "") or ""
    R["running"] = s.get("running")
    R["connectors"] = list((eng.get("connectors") or {}).keys())
    R["ready"] = ready
    R["orders"] = "active" if ("Level" in fs or ("buy" in fs.lower() and "sell" in fs.lower())) else "none"
    lg = cli("logs", instance, "-n", "60", timeout=60)
    raw = lg.get("_raw", "") if isinstance(lg, dict) else str(lg)
    errs = [ln for ln in raw.splitlines() if "ERROR" in ln or "CRITICAL" in ln or "Traceback" in ln]
    R["log_error"] = errs[-1][:200] if errs else ""

    if update_key:
        up = cli("update", instance, update_key, "0.6" if "spread" in update_key else "25", "--json", timeout=60)
        R["update"] = {"key": update_key, "ok": up.get("ok"), "live": up.get("applied_live"),
                       "note": (up.get("note") or up.get("error") or "")[:70]}
    else:
        R["update"] = "no-updatable-key-picked"

    h = cli("history", instance, "--json", timeout=60)
    R["history"] = "ok" if h.get("ok") else f"FAIL:{(h.get('error') or h.get('_raw', '') or '')[:120]}"
    t = cli("trades", instance, "--json", timeout=60)
    R["trades"] = t.get("count") if t.get("ok") else f"FAIL:{(t.get('error') or '')[:120]}"

    sp = cli("stop", instance, "--json", timeout=90)
    R["stop"] = "ok" if sp.get("ok") and sp.get("stopped") else f"FAIL:{sp.get('error') or sp.get('_raw', '')[:200]}"
    print(json.dumps(R, indent=2))


if __name__ == "__main__":
    main()
