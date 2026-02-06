#!/bin/bash
# Update and restart WEEX Trading Bot Services

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Updating WEEX Trading Bot services...${NC}"

# Pull latest code (if using git)
echo -e "${GREEN}Pulling latest code...${NC}"
git pull || echo "Not a git repository or no updates available"

# Rebuild images
echo -e "${GREEN}Rebuilding Docker images...${NC}"
sudo docker-compose -f docker-compose.prod.yml build --no-cache

# Restart services with downtime
echo -e "${YELLOW}Restarting services...${NC}"
sudo docker-compose -f docker-compose.prod.yml down
sudo docker-compose -f docker-compose.prod.yml up -d

echo -e "${GREEN}Update complete!${NC}"
echo ""
./monitor.sh
