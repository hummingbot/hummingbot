#!/bin/bash
# WEEX Production Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}WEEX Trading Bot Deployment${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo -e "Creating .env from .env.example..."

    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env file with your actual credentials before proceeding${NC}"
        echo -e "${RED}Exiting...${NC}"
        exit 1
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Create necessary directories
echo -e "${GREEN}Creating directory structure...${NC}"
mkdir -p logs/mm logs/vol data/mm data/vol health certs
chmod 755 logs/mm logs/vol data/mm data/vol health

# Build images
echo -e "${GREEN}Building Docker images...${NC}"
docker-compose -f docker-compose.prod.yml build

# Start services
echo -e "${GREEN}Starting services...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to start
echo -e "${GREEN}Waiting for services to start...${NC}"
sleep 10

# Show status
echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Deployment Status${NC}"
echo -e "${GREEN}=====================================${NC}"
docker-compose -f docker-compose.prod.yml ps

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Service URLs${NC}"
echo -e "${GREEN}=====================================${NC}"
echo -e "Monitoring Dashboard: ${YELLOW}http://localhost:8501${NC}"
echo ""

# Show logs command
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Useful Commands${NC}"
echo -e "${GREEN}=====================================${NC}"
echo -e "View all logs:         ${YELLOW}docker-compose -f docker-compose.prod.yml logs -f${NC}"
echo -e "View MM bot logs:      ${YELLOW}docker-compose -f docker-compose.prod.yml logs -f hummingbot-mm${NC}"
echo -e "View Vol bot logs:     ${YELLOW}docker-compose -f docker-compose.prod.yml logs -f hummingbot-vol${NC}"
echo -e "View dashboard logs:   ${YELLOW}docker-compose -f docker-compose.prod.yml logs -f monitor-dashboard${NC}"
echo -e "Stop all services:     ${YELLOW}docker-compose -f docker-compose.prod.yml down${NC}"
echo -e "Restart a service:     ${YELLOW}docker-compose -f docker-compose.prod.yml restart <service-name>${NC}"
echo -e "Shell into MM bot:     ${YELLOW}docker exec -it weex-market-maker bash${NC}"
echo -e "Shell into Vol bot:    ${YELLOW}docker exec -it weex-volume-generator bash${NC}"
echo ""

echo -e "${GREEN}Deployment complete!${NC}"
