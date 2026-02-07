# Log Rotation Configuration

This document describes the comprehensive log rotation setup for the Hummingbot WEEX market-making system.

## Overview

Log rotation is configured at **three levels**:
1. **Application-level**: Python logging handlers with size/time-based rotation
2. **Container-level**: Docker daemon json-file driver with size-based rotation
3. **Host-level**: Linux logrotate utility with daily/weekly rotation

This multi-layered approach ensures logs never consume excessive disk space.

---

## 1. Application-Level Log Rotation

### Hummingbot Bots (MM & VOL)
- **Handler**: `TimedRotatingFileHandler` (daily rotation)
- **Rotation Trigger**: Daily at midnight
- **Backup Count**: 7 days of history
- **Log Files**:
  - Market Making: `/home/hummingbot/logs/logs_weex_vcc_pmm.log`
  - Volume Generator: `/home/hummingbot/logs/logs_weex_volume_generator.log`
- **Configuration**: `hummingbot/templates/hummingbot_logs_TEMPLATE.yml`

```yaml
file_handler:
  class: logging.handlers.TimedRotatingFileHandler
  filename: $PROJECT_DIR/logs/logs_$STRATEGY_FILE_PATH.log
  when: "D"        # Daily rotation
  interval: 1      # Every 1 day
  backupCount: 7   # Keep 7 backup files
```

### Monitor Service (`weex_monitor_standalone.py`)
- **Handler**: `RotatingFileHandler` (size-based rotation)
- **Rotation Trigger**: When file reaches 10 MB
- **Backup Count**: 5 rotated files
- **Log File**: `/home/hummingbot/logs/weex_monitor.log`

```python
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5
)
```

---

## 2. Container-Level Log Rotation

Docker daemon manages logs for containerized services using the json-file driver:

### hummingbot-mm & hummingbot-vol
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"    # Rotate when single log reaches 50 MB
    max-file: "10"     # Keep 10 rotated files
```

**Impact**: Even if Python logging doesn't catch everything, Docker prevents unbounded growth.

### weex-monitor-api
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"    # Rotate when log reaches 10 MB
    max-file: "5"      # Keep 5 rotated files
```

**Legacy Note**: Dashboard (Streamlit) logs to stdout, captured by Docker driver.

---

## 3. Host-Level Log Rotation (Optional)

Linux `logrotate` provides an additional safety layer.

### Installation

```bash
# Copy configuration (requires sudo)
sudo cp logrotate.conf /etc/logrotate.d/hummingbot-weex

# Verify configuration (doesn't run rotation, just checks)
sudo logrotate -d /etc/logrotate.d/hummingbot-weex

# Force immediate rotation (useful for testing)
sudo logrotate -f /etc/logrotate.d/hummingbot-weex

# Check when logrotate will run
sudo ls -la /etc/logrotate.d/hummingbot-weex
```

### Configuration Details

**MM Bot Logs**:
- Rotation: Daily
- History: 14 days
- Compressed: Yes (saves ~90% space)

**Monitor Logs**:
- Rotation: Daily
- History: 7 days
- Compressed: Yes

**Data Files**:
- Rotation: Weekly
- History: 4 weeks
- Compressed: Yes

---

## Monitoring Log Growth

### Check Current Log Sizes

```bash
# Total log directory size
du -sh /home/jkovacs/git/hummingbot/logs/

# Largest files
find /home/jkovacs/git/hummingbot/logs -type f -exec du -h {} + | sort -rh | head -20

# Count log files (including rotated files)
find /home/jkovacs/git/hummingbot/logs -type f -name "*.log*" | wc -l

# Check Docker container logs
docker logs weex-market-maker 2>&1 | wc -l  # line count
```

### Set Up Monitoring

```bash
# Watch log growth in real-time
watch -n 5 'du -sh /home/jkovacs/git/hummingbot/logs/*'

# Alert on log growth (adds to crontab)
# @hourly if [ $(du -sk /home/jkovacs/git/hummingbot/logs | cut -f1) -gt 5242880 ]; then echo "Logs exceed 5GB"; fi
```

---

## Troubleshooting Log Rotation

### Rotation Not Happening

1. **Check Python logging config**:
   ```bash
   sudo docker exec weex-market-maker cat /home/hummingbot/conf/hummingbot_logs.yml | grep -A 5 "file_handler"
   ```

2. **Check Docker daemon config**:
   ```bash
   docker inspect weex-market-maker | grep -A 10 '"LogConfig"'
   ```

3. **Manually trigger rotation**:
   ```bash
   # For TimedRotatingFileHandler (Python), recreate container or restart app
   sudo docker compose -f docker-compose.prod.yml restart hummingbot-mm

   # For Docker json-file driver (automatic, no action needed)
   ```

### Logs Still Growing Too Fast

- Reduce `backupCount` in Python handlers
- Increase `interval` (e.g., "H" for hourly instead of "D" for daily)
- Reduce `max-size` in Docker logging
- Check for excessive debug logging (`WEEX_MONITOR_CONSOLE_LEVEL=DEBUG` increases verbosity)

---

## Estimated Disk Usage

### Typical Production Load

Based on market-making bot with ~30 orders refreshed every 60 seconds:

| Component | Per Day | Per Week | Per Month |
|-----------|---------|----------|-----------|
| MM Bot Log | ~50-100 MB | ~350-700 MB | 1.5-3 GB |
| Monitor Log | ~10-20 MB | ~70-140 MB | 300-600 MB |
| Data Files | ~5-10 MB | ~35-70 MB | 150-300 MB |
| **Total** | **65-130 MB** | **455-910 MB** | **1.95-3.9 GB** |

**With Compression**: ~70% reduction, so multiply above by 0.3

### Cleanup Old Logs

```bash
# List files older than 30 days
find /home/jkovacs/git/hummingbot/logs -type f -mtime +30 -name "*.log*"

# Delete files older than 30 days
find /home/jkovacs/git/hummingbot/logs -type f -mtime +30 -name "*.log*" -delete

# Archive to external storage
tar -czf hummingbot_logs_$(date +%Y%m%d).tar.gz /home/jkovacs/git/hummingbot/logs/
mv hummingbot_logs_*.tar.gz /backup/location/
```

---

## Summary

✅ **Multi-layered log rotation ensures**:
- Python logging rotates daily/size-based
- Docker rotates when containers exceed max-size
- Logrotate provides system-level oversight
- No single component can cause unbounded disk growth
- Compressed backups save ~90% of disk space
- 7-14 days of history retained for debugging

**No further action needed** unless experiencing specific issues with log growth or needing to adjust retention periods.
