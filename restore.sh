#!/bin/bash
# Restore WEEX Trading Bot Data from Backup

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "$1" ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo -e "Usage: $0 <backup-file>"
    echo ""
    echo -e "${YELLOW}Available backups:${NC}"
    ls -lh backups/
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}WEEX Trading Bot Restore${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

echo -e "${YELLOW}Restoring from: $BACKUP_FILE${NC}"
echo ""

# Stop services first
echo -e "${YELLOW}Stopping services...${NC}"
./stop.sh

# Backup current state
echo -e "${YELLOW}Backing up current state...${NC}"
./backup.sh

# Restore from backup
echo -e "${YELLOW}Restoring data...${NC}"
tar -xzf "$BACKUP_FILE"

echo -e "${GREEN}Restore complete!${NC}"
echo ""
echo -e "${YELLOW}Start services with: ./deploy.sh${NC}"
