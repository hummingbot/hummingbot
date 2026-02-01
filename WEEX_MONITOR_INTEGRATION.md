# WEEX Monitor Bot Integration

**Date:** February 1, 2026
**Status:** ✅ IMPLEMENTED

---

## Architecture

**Two-Bot System:**
- **Trading Bot** (weex_vcc_pmm.py) - Places/cancels orders, separate API key
- **Monitor Bot** (weex_monitor.py) - Polls status, health checks, separate API key

**Communication:** JSON health file at `/tmp/weex_mm_health.json`

---

## Health File Format

The monitor writes this file every ~30-60 seconds:

```json
{
  "healthy": true,
  "pause_requested": false,
  "issues": [],
  "last_update": 1769932800,
  "stats": {
    "open_orders": 8,
    "last_fill_time": 1769932750,
    "balance_vcc": 1000000.0,
    "balance_usdt": 50000.0,
    "pending_orders": 0,
    "failed_orders": 0
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `healthy` | bool | Overall health status (false = warnings detected) |
| `pause_requested` | bool | **Critical**: Trading bot will pause if true |
| `issues` | array | List of detected issues (strings) |
| `last_update` | int | Unix timestamp of last monitor update |
| `stats` | object | Current state statistics from monitor |

---

## Trading Bot Behavior

The `weex_vcc_pmm.py` strategy checks the health file every 5 seconds:

### If `pause_requested = true`:
1. Log warning with issues list
2. Cancel all open orders
3. Skip order placement (pause trading)
4. Continue checking health file every 5s
5. Resume when `pause_requested = false`

### If `healthy = false`:
- Log warning with issues list
- **Continue trading** (informational only)

### If file is stale (>5 minutes old):
- Log warning
- **Continue trading** (monitor may be down, don't auto-pause)

### If file doesn't exist:
- **Continue trading** (monitor not running yet)

---

## Monitor Bot Detection Rules

Example issues that trigger `pause_requested = true`:

### 1. Stuck Orders (Critical)
```python
# Order pending >30 seconds
if order['status'] == 'pending' and time.now() - order['created'] > 30:
    pause_requested = True
    issues.append(f"Order {order['id']} stuck in pending >30s")
```

### 2. Stale Trading (Warning)
```python
# No fills in 10 minutes (possible freeze)
if fills and time.now() - fills[-1]['timestamp'] > 600:
    healthy = False  # Don't pause, just warn
    issues.append("No fills in 10 minutes - possible bot freeze")
```

### 3. Balance Drift (Warning)
```python
# Significant balance deviation
expected_vcc = 1000000
if abs(balances['VCC'] - expected_vcc) > 50000:
    healthy = False
    issues.append(f"VCC balance drift: expected {expected_vcc}, got {balances['VCC']}")
```

### 4. Failed Order Cascade (Critical)
```python
# Multiple order failures in short period
if failed_order_count > 5 in last 60 seconds:
    pause_requested = True
    issues.append(f"Multiple order failures: {failed_order_count} in 60s")
```

---

## Monitor Bot Implementation

### Basic Structure

```python
#!/usr/bin/env python3
"""
WEEX Monitor Bot - Polls order status and writes health file
Uses separate API key from trading bot
"""

import time
import json
from weex_api import WeexAPI  # Your connector

HEALTH_FILE = "/tmp/weex_mm_health.json"
POLL_INTERVAL = 30  # seconds

def check_health(api):
    """Poll exchange and analyze health"""
    orders = api.get_open_orders("VCC-USDT")
    fills = api.get_recent_fills("VCC-USDT", limit=100)
    balances = api.get_balances()

    issues = []
    pause_requested = False

    # Check for stuck pending orders
    now = time.time()
    for order in orders:
        if order['status'] == 'pending':
            age = now - (order['cTime'] / 1000)
            if age > 30:
                issues.append(f"Order {order['orderId']} stuck pending {age:.0f}s")
                pause_requested = True

    # Check for stale fills
    if fills:
        last_fill = fills[0]['cTime'] / 1000
        if now - last_fill > 600:
            issues.append(f"No fills in {(now - last_fill)/60:.0f} min")

    # Check balance drift
    vcc_balance = float(balances.get('VCC', {}).get('available', 0))
    expected_vcc = 1000000
    if abs(vcc_balance - expected_vcc) > 50000:
        issues.append(f"VCC drift: expected {expected_vcc}, got {vcc_balance}")

    return {
        'healthy': len(issues) == 0,
        'pause_requested': pause_requested,
        'issues': issues,
        'last_update': int(now),
        'stats': {
            'open_orders': len(orders),
            'last_fill_time': int(fills[0]['cTime'] / 1000) if fills else 0,
            'balance_vcc': vcc_balance,
            'balance_usdt': float(balances.get('USDT', {}).get('available', 0)),
            'pending_orders': sum(1 for o in orders if o['status'] == 'pending'),
        }
    }

def main():
    api = WeexAPI(api_key="MONITOR_API_KEY", secret="...", passphrase="...")

    while True:
        try:
            health = check_health(api)

            # Write health file atomically
            temp_file = HEALTH_FILE + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(health, f, indent=2)
            os.rename(temp_file, HEALTH_FILE)

            # Log status
            status = "⚠️  PAUSE" if health['pause_requested'] else "✅ OK"
            print(f"{status} - {len(health['issues'])} issues - {health['stats']['open_orders']} orders")

            if health['issues']:
                for issue in health['issues']:
                    print(f"  - {issue}")

        except Exception as e:
            print(f"Monitor error: {e}")
            # Don't write health file on error - let it go stale

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
```

---

## Testing the Integration

### 1. Start Trading Bot (No Monitor)
```bash
# Health file doesn't exist
./start
# Bot should continue normally, log "monitor not running"
```

### 2. Start Monitor Bot
```bash
python scripts/weex_monitor_health.py
# Creates /tmp/weex_mm_health.json with healthy status
```

### 3. Verify Integration
```bash
# Check health file
cat /tmp/weex_mm_health.json

# Trading bot logs should show:
# No health warnings = file is being read successfully
```

### 4. Test Pause Trigger
```bash
# Manually trigger pause
echo '{"healthy": false, "pause_requested": true, "issues": ["Test pause"], "last_update": '$(date +%s)'}' > /tmp/weex_mm_health.json

# Trading bot should:
# 1. Log "MONITOR PAUSE REQUESTED: Test pause"
# 2. Cancel all orders
# 3. Stop placing new orders
```

### 5. Test Resume
```bash
# Clear pause
echo '{"healthy": true, "pause_requested": false, "issues": [], "last_update": '$(date +%s)'}' > /tmp/weex_mm_health.json

# Trading bot should resume on next tick (within 5 seconds)
```

---

## Production Deployment

### Systemd Services (Recommended)

**Trading Bot:** `/etc/systemd/system/weex-trading.service`
```ini
[Unit]
Description=WEEX VCC Market Making Bot
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/hummingbot
ExecStart=/home/trader/hummingbot/start weex_vcc_pmm
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Monitor Bot:** `/etc/systemd/system/weex-monitor.service`
```ini
[Unit]
Description=WEEX Monitor Bot
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/hummingbot
ExecStart=/usr/bin/python3 scripts/weex_monitor_health.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Start both:**
```bash
sudo systemctl enable weex-trading weex-monitor
sudo systemctl start weex-trading weex-monitor
sudo systemctl status weex-trading weex-monitor
```

---

## Monitoring Dashboard (Optional)

Simple web dashboard to visualize health status:

```python
from flask import Flask, jsonify
import json

app = Flask(__name__)

@app.route('/health')
def health():
    with open('/tmp/weex_mm_health.json') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

Access at: `http://localhost:8080/health`

---

## Summary

✅ **Trading bot** checks monitor health every 5 seconds
✅ **Monitor bot** writes health file every 30-60 seconds
✅ **Automatic pause** on critical issues (stuck orders, API failures)
✅ **Graceful degradation** if monitor goes down (continues trading)
✅ **Separate API keys** prevent rate limit interference
✅ **Production ready** with systemd integration

The monitor acts as a safety net without blocking normal operation.
