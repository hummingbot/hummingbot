#!/bin/bash
# Stop WEEX Trading Bot Services

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping WEEX Trading Bot services...${NC}"

# Stop all services
sudo docker-compose -f docker-compose.prod.yml down

echo -e "${GREEN}All services stopped${NC}"
echo ""
echo -e "${YELLOW}Note: Data in volumes (logs, data, health) is preserved${NC}"
echo -e "To remove volumes, run: ${RED}sudo docker-compose -f docker-compose.prod.yml down -v${NC}"
