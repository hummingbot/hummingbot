#!/bin/bash
# Backup WEEX Trading Bot Data

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/weex_backup_$TIMESTAMP.tar.gz"

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}WEEX Trading Bot Backup${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Creating backup...${NC}"

# Create backup
tar -czf "$BACKUP_FILE" \
  --exclude='logs/*.log.*' \
  --exclude='data/*snapshots*' \
  logs/ \
  data/ \
  conf/ \
  health/ \
  .env \
  2>/dev/null || true

# Get backup size
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo -e "${GREEN}Backup created successfully!${NC}"
echo -e "File: ${YELLOW}$BACKUP_FILE${NC}"
echo -e "Size: ${YELLOW}$SIZE${NC}"
echo ""

# List recent backups
echo -e "${YELLOW}Recent backups:${NC}"
ls -lh "$BACKUP_DIR" | tail -5

# Clean old backups (keep last 10)
echo ""
echo -e "${YELLOW}Cleaning old backups (keeping last 10)...${NC}"
cd "$BACKUP_DIR"
ls -t | tail -n +11 | xargs -r rm --
cd ..

echo ""
echo -e "${GREEN}Backup complete!${NC}"
