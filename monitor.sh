#!/bin/bash
# Monitor WEEX Trading Bot Services

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}WEEX Trading Bot Status${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Show container status
echo -e "${YELLOW}Container Status:${NC}"
sudo docker-compose -f docker-compose.prod.yml ps
echo ""

# Show health status
echo -e "${YELLOW}Health Checks:${NC}"
sudo docker inspect weex-market-maker --format='{{.State.Health.Status}}' 2>/dev/null && echo "Market Maker: $(sudo docker inspect weex-market-maker --format='{{.State.Health.Status}}')" || echo "Market Maker: Not running"
sudo docker inspect weex-volume-generator --format='{{.State.Health.Status}}' 2>/dev/null && echo "Volume Generator: $(sudo docker inspect weex-volume-generator --format='{{.State.Health.Status}}')" || echo "Volume Generator: Not running"
sudo docker inspect weex-monitor-dashboard --format='{{.State.Health.Status}}' 2>/dev/null && echo "Dashboard: $(sudo docker inspect weex-monitor-dashboard --format='{{.State.Health.Status}}')" || echo "Dashboard: Not running"
echo ""

# Show resource usage
echo -e "${YELLOW}Resource Usage:${NC}"
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" weex-market-maker weex-volume-generator weex-monitor-dashboard weex-monitor-api 2>/dev/null || echo "No containers running"
echo ""

# Show recent logs
echo -e "${YELLOW}Recent Activity (last 10 lines per service):${NC}"
echo ""
echo -e "${GREEN}Market Maker:${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=10 hummingbot-mm 2>/dev/null || echo "Not running"
echo ""
echo -e "${GREEN}Volume Generator:${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=10 hummingbot-vol 2>/dev/null || echo "Not running"
echo ""

echo -e "${GREEN}=====================================${NC}"
echo -e "Dashboard: ${YELLOW}http://localhost:8501${NC}"
echo -e "${GREEN}=====================================${NC}"
