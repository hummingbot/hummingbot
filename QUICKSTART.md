# WEEX Trading Bot - Quick Start Guide

Get your containerized WEEX trading bot running in 5 minutes!

## 🚀 Quick Deployment (5 Steps)

### 1. Configure Credentials

```bash
# Copy environment template
cp .env.example .env

# Edit with your API credentials
nano .env  # or use your preferred editor
```

Add your WEEX API keys for both accounts (Market Making + Volume Generation).

### 2. Run Pre-flight Check

```bash
./preflight.sh
```

This validates:
- ✅ Docker is installed and running
- ✅ Required files exist
- ✅ Environment variables are set
- ✅ System resources are sufficient
- ✅ Network connectivity to WEEX

### 3. Deploy Services

```bash
./deploy.sh
```

This will:
- Create necessary directories
- Build Docker images
- Start all services
- Display service URLs

### 4. Verify Deployment

```bash
# Check service status
./monitor.sh

# Or using make
make -f Makefile.prod prod-check
```

### 5. Access Monitoring

Open your browser to: **http://localhost:8501**

You should see the Streamlit monitoring dashboard showing:
- Both bot health status
- Recent activity logs
- Real-time metrics

## 📦 What Gets Deployed

| Service | Container Name | Purpose |
|---------|----------------|---------|
| Market Maker Bot | `weex-market-maker` | Runs weex_vcc_pmm.py strategy |
| Volume Generator | `weex-volume-generator` | Runs volume generation |
| Monitor Dashboard | `weex-monitor-dashboard` | Streamlit UI on port 8501 |
| Monitor API | `weex-monitor-api` | Backend monitoring service |

## 🛠️ Common Commands

### Using Scripts

```bash
./deploy.sh      # Deploy all services
./monitor.sh     # View status
./stop.sh        # Stop all services
./backup.sh      # Backup data
./update.sh      # Update and restart
./preflight.sh   # Run pre-flight checks
```

### Using Make

```bash
make -f Makefile.prod prod-deploy      # Deploy
make -f Makefile.prod prod-status      # Status
make -f Makefile.prod prod-logs-mm     # MM logs
make -f Makefile.prod prod-logs-vol    # Vol logs
make -f Makefile.prod prod-backup      # Backup
make -f Makefile.prod prod-check       # Quick check
```

### Docker Compose Direct

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart specific service
docker-compose -f docker-compose.prod.yml restart hummingbot-mm

# Stop everything
docker-compose -f docker-compose.prod.yml down
```

## 📊 Monitoring

### Dashboard (Web UI)
- URL: http://localhost:8501
- Shows: Both bots health, logs, metrics
- Auto-refresh: Configurable in sidebar

### Command Line

```bash
# Service status
docker-compose -f docker-compose.prod.yml ps

# Health checks
docker inspect weex-market-maker --format='{{.State.Health.Status}}'
docker inspect weex-volume-generator --format='{{.State.Health.Status}}'

# Resource usage
docker stats

# Live logs
docker-compose -f docker-compose.prod.yml logs -f hummingbot-mm
```

## 🔐 Security Checklist

Before production deployment:

- [ ] Environment variables set in `.env` (never commit this!)
- [ ] API keys have IP whitelisting enabled on WEEX
- [ ] Trading keys have withdrawal disabled
- [ ] Monitoring keys are read-only
- [ ] Different passwords for each bot instance
- [ ] `.env` is in `.gitignore`
- [ ] Regular backup schedule configured
- [ ] Firewall rules configured (if applicable)

## 📁 Directory Layout

```
.
├── docker-compose.prod.yml    # Production config
├── .env                        # Your credentials (DO NOT COMMIT)
├── .env.example               # Template
│
├── logs/
│   ├── mm/                    # Market maker logs
│   └── vol/                   # Volume generator logs
│
├── data/
│   ├── mm/                    # Market maker data
│   └── vol/                   # Volume generator data
│
├── health/                    # Health check files
├── backups/                   # Backup archives
│
└── scripts/
    ├── weex_vcc_pmm.py       # Market making strategy
    └── weex_volume_generator.py
```

## 🆘 Troubleshooting

### Services Won't Start

```bash
# Check error logs
docker-compose -f docker-compose.prod.yml logs

# Verify environment
cat .env

# Re-run preflight
./preflight.sh
```

### Can't Access Dashboard

```bash
# Check if port is available
netstat -tuln | grep 8501

# Check dashboard logs
docker-compose -f docker-compose.prod.yml logs monitor-dashboard

# Restart dashboard
docker-compose -f docker-compose.prod.yml restart monitor-dashboard
```

### Bot Not Trading

```bash
# Check bot logs
docker-compose -f docker-compose.prod.yml logs -f hummingbot-mm

# Shell into container
docker exec -it weex-market-maker bash

# Verify API connectivity
docker exec weex-market-maker curl https://api-spot.weex.com
```

### High Memory Usage

```bash
# Check resource usage
docker stats

# Restart problematic service
docker-compose -f docker-compose.prod.yml restart <service-name>
```

## 🔄 Updates and Maintenance

### Update Code and Restart

```bash
./update.sh
```

### Backup Before Changes

```bash
./backup.sh
```

### View Backups

```bash
ls -lh backups/
```

### Restore from Backup

```bash
./restore.sh backups/weex_backup_YYYYMMDD_HHMMSS.tar.gz
```

## 📚 Additional Resources

- [Full Deployment Documentation](DOCKER_DEPLOYMENT.md)
- [WEEX Production Setup](WEEX_PRODUCTION_DEPLOYMENT.md)
- [Pre-Launch Checklist](PRE_LAUNCH_CHECKLIST.md)
- [WEEX Quick Start](WEEX_MM_QUICKSTART.md)

## 💡 Tips

1. **Run preflight check** before every deployment
2. **Backup regularly** - set up a cron job
3. **Monitor logs** daily for first week
4. **Start with smaller amounts** to test
5. **Use screen/tmux** if deploying without systemd
6. **Enable notifications** for critical events
7. **Review health dashboard** at least daily

## 🎯 Next Steps

After successful deployment:

1. ✅ Monitor for 24 hours
2. ✅ Verify both bots are trading as expected
3. ✅ Check health dashboard regularly
4. ✅ Set up automated backups
5. ✅ Configure alerts/notifications
6. ✅ Document any custom configuration
7. ✅ Plan for scaling if needed

---

**Need Help?** Check the troubleshooting section in [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
