# WEEX Trading Bot - Containerized Deployment

Complete Docker-based deployment solution for running WEEX trading bots with monitoring.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Host                               │
│                                                              │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │  Market Maker Bot  │  │ Volume Gen Bot     │            │
│  │  (weex-market-     │  │ (weex-volume-      │            │
│  │   maker)           │  │  generator)        │            │
│  │                    │  │                    │            │
│  │  • weex_vcc_pmm.py │  │  • volume_gen.py   │            │
│  │  • Separate config │  │  • Separate config │            │
│  │  • Separate logs   │  │  • Separate logs   │            │
│  └────────────────────┘  └────────────────────┘            │
│                                                              │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │  Monitor Dashboard │  │  Monitor API       │            │
│  │  (Streamlit)       │  │  (Standalone)      │            │
│  │  Port: 8501       │  │                    │            │
│  └────────────────────┘  └────────────────────┘            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │             Shared Volumes                             │ │
│  │  • logs/mm, logs/vol                                   │ │
│  │  • data/mm, data/vol                                   │ │
│  │  • health (shared health monitoring)                   │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM
- 20GB+ disk space
- Linux/macOS (Windows WSL2 supported)

## 🚀 Quick Start

### 1. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your WEEX API credentials
nano .env
```

### 2. Deploy All Services

```bash
# Deploy everything with one command
./deploy.sh
```

This script will:
- ✅ Create necessary directories
- ✅ Build Docker images
- ✅ Start all services
- ✅ Display service URLs and useful commands

### 3. Access Services

- **Monitoring Dashboard**: http://localhost:8501
- **Container logs**: `docker-compose -f docker-compose.prod.yml logs -f`

## 📁 Directory Structure

```
hummingbot/
├── docker-compose.prod.yml   # Production deployment config
├── Dockerfile                 # Main Hummingbot image
├── Dockerfile.monitor         # Monitoring dashboard image
├── .env.example              # Environment template
├── .env                      # Your credentials (gitignored)
├── deploy.sh                 # Deployment script
├── stop.sh                   # Stop all services
├── monitor.sh                # Status monitoring
├── update.sh                 # Update and restart
│
├── logs/
│   ├── mm/                   # Market maker logs
│   └── vol/                  # Volume generator logs
│
├── data/
│   ├── mm/                   # Market maker data
│   └── vol/                  # Volume generator data
│
├── health/                   # Health check files
├── conf/                     # Configuration files
│   ├── connectors/           # Exchange configs
│   ├── strategies/           # Strategy configs
│   └── scripts/              # Script configs
│
└── scripts/
    ├── weex_vcc_pmm.py      # Market making strategy
    └── weex_volume_generator.py  # Volume generation
```

## 🔧 Management Commands

### View Status

```bash
./monitor.sh
```

Shows:
- Container status
- Health checks
- Resource usage
- Recent logs

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f hummingbot-mm
docker-compose -f docker-compose.prod.yml logs -f hummingbot-vol
docker-compose -f docker-compose.prod.yml logs -f monitor-dashboard
```

### Stop Services

```bash
./stop.sh
```

### Restart a Specific Service

```bash
docker-compose -f docker-compose.prod.yml restart hummingbot-mm
docker-compose -f docker-compose.prod.yml restart hummingbot-vol
```

### Access Container Shell

```bash
# Market maker
docker exec -it weex-market-maker bash

# Volume generator
docker exec -it weex-volume-generator bash
```

### Update and Redeploy

```bash
./update.sh
```

Performs:
- Pull latest code
- Rebuild images
- Restart services

## 🔐 Security Best Practices

### API Key Setup

Each bot instance needs **2 API key pairs**:

1. **Trading Keys**: Used by Hummingbot
   - Permissions: Trading only (NO withdrawal)
   - IP Whitelist: Your server IP

2. **Monitoring Keys**: Used by monitoring services
   - Permissions: Read-only
   - IP Whitelist: Your monitoring IP

### Environment Variables

```bash
# Market Making Bot (Trading Keys)
WEEX_MM_API_KEY=...
WEEX_MM_API_SECRET=...
WEEX_MM_PASSPHRASE=...

# Market Making Bot (Monitoring Keys)
WEEX_MM_MONITOR_API_KEY=...
WEEX_MM_MONITOR_API_SECRET=...
WEEX_MM_MONITOR_PASSPHRASE=...

# Volume Generation Bot (Trading Keys)
WEEX_VOL_API_KEY=...
WEEX_VOL_API_SECRET=...
WEEX_VOL_PASSPHRASE=...

# Volume Generation Bot (Monitoring Keys)
WEEX_VOL_MONITOR_API_KEY=...
WEEX_VOL_MONITOR_API_SECRET=...
WEEX_VOL_MONITOR_PASSPHRASE=...
```

### Security Checklist

- ✅ Never commit `.env` file
- ✅ Use IP whitelisting on all API keys
- ✅ Disable withdrawal permissions
- ✅ Rotate API keys regularly
- ✅ Use different passwords per environment
- ✅ Keep monitoring keys read-only
- ✅ Regularly review API key usage logs

## 🏥 Health Monitoring

### Health Check Endpoints

Each service has automatic health checks:

- **Bots**: Check for health JSON file presence
- **Dashboard**: HTTP health endpoint
- **Frequency**: Every 30 seconds

### View Health Status

```bash
docker inspect weex-market-maker --format='{{.State.Health.Status}}'
docker inspect weex-volume-generator --format='{{.State.Health.Status}}'
docker inspect weex-monitor-dashboard --format='{{.State.Health.Status}}'
```

### Health File Locations

```
health/
├── weex_mm_health.json      # Market maker health
└── weex_vol_health.json     # Volume generator health
```

## 📊 Resource Requirements

### Minimum Requirements

- **CPU**: 2 cores
- **RAM**: 4GB
- **Disk**: 20GB
- **Network**: Stable connection

### Recommended for Production

- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Disk**: 50GB+ SSD
- **Network**: Low-latency connection

### Container Resource Usage

| Service | CPU | RAM | Notes |
|---------|-----|-----|-------|
| hummingbot-mm | ~50% | 500MB | Market maker |
| hummingbot-vol | ~50% | 500MB | Volume gen |
| monitor-dashboard | ~10% | 200MB | Streamlit UI |
| monitor-api | ~5% | 100MB | Monitoring |

## 🔄 Backup and Restore

### Backup Data

```bash
# Backup all data
tar -czf backup-$(date +%Y%m%d).tar.gz \
  logs/ data/ conf/ health/ .env
```

### Restore Data

```bash
# Extract backup
tar -xzf backup-YYYYMMDD.tar.gz

# Restart services
./deploy.sh
```

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs <service-name>

# Check environment
docker-compose -f docker-compose.prod.yml config

# Rebuild clean
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

### High Memory Usage

```bash
# Check stats
docker stats

# Restart specific service
docker-compose -f docker-compose.prod.yml restart <service-name>
```

### Connection Issues

```bash
# Check network
docker network inspect hummingbot_hummingbot-network

# Check container connectivity
docker exec weex-market-maker ping -c 3 api-spot.weex.com
```

### Dashboard Not Accessible

```bash
# Check if port is in use
netstat -tulpn | grep 8501

# Check dashboard logs
docker-compose -f docker-compose.prod.yml logs monitor-dashboard

# Restart dashboard
docker-compose -f docker-compose.prod.yml restart monitor-dashboard
```

## 🔄 Updating Configuration

### Update Strategy Configuration

1. Edit strategy files in `scripts/`
2. Restart the specific bot:

```bash
docker-compose -f docker-compose.prod.yml restart hummingbot-mm
```

### Update Environment Variables

1. Edit `.env` file
2. Restart services:

```bash
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

## 📈 Scaling

### Add More Bot Instances

1. Copy service definition in `docker-compose.prod.yml`
2. Update service name, container name, and volumes
3. Add environment variables to `.env`
4. Deploy:

```bash
docker-compose -f docker-compose.prod.yml up -d <new-service-name>
```

## 📝 Logs Management

### Log Rotation

Logs are automatically rotated:
- **Max size**: 50MB per file
- **Max files**: 10 files
- **Total**: ~500MB per service

### View Specific Time Range

```bash
# Since specific time
docker-compose -f docker-compose.prod.yml logs --since="2026-02-05T10:00:00"

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

## 🆘 Support

### Common Issues

| Issue | Solution |
|-------|----------|
| Out of memory | Increase Docker memory limit |
| Connection timeout | Check WEEX API status, firewall rules |
| API rate limit | Review strategy configuration |
| Container crash loop | Check logs, verify API credentials |

### Getting Help

1. Check logs: `./monitor.sh`
2. Review documentation: `WEEX_*.md` files
3. Check container health: `docker ps`
4. Review environment: `.env` file

## 📜 License

See [LICENSE](LICENSE) file.

## 🔗 Related Documentation

- [WEEX Production Deployment](WEEX_PRODUCTION_DEPLOYMENT.md)
- [WEEX Quickstart](WEEX_MM_QUICKSTART.md)
- [WEEX Monitor Integration](WEEX_MONITOR_INTEGRATION.md)
- [Pre-Launch Checklist](PRE_LAUNCH_CHECKLIST.md)
