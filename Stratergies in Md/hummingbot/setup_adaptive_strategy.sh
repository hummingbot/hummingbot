#!/bin/bash
# Setup script for Adaptive Market Making Strategy

# Exit on any error
set -e

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up Adaptive Market Making Strategy...${NC}"

# Check if Python 3.8+ is installed
python_version=$(python3 --version 2>&1 | awk '{print $2}')
if [[ ! $python_version =~ ^3\.[89]\. && ! $python_version =~ ^3\.1[0-9]\. ]]; then
    echo -e "${RED}Error: Python 3.8 or higher is required. Found: $python_version${NC}"
    echo "Please install Python 3.8 or higher before continuing."
    exit 1
fi

# Check if we're in the hummingbot directory
if [ ! -d "scripts" ]; then
    echo -e "${RED}Error: Please run this script from the hummingbot directory.${NC}"
    exit 1
fi

# Create required directories if they don't exist
echo -e "${GREEN}Creating required directories...${NC}"
mkdir -p scripts/strategies
mkdir -p conf
mkdir -p logs
mkdir -p data/models

# Install requirements
echo -e "${GREEN}Installing requirements...${NC}"
pip install -r requirements.txt

# Optional ML dependencies
read -p "Install machine learning dependencies? (y/n) " ml_deps
if [[ $ml_deps == "y" || $ml_deps == "Y" ]]; then
    echo -e "${GREEN}Installing ML dependencies...${NC}"
    pip install tensorflow torch tensorboard
fi

# Create a virtual environment if requested
read -p "Create a dedicated virtual environment? (y/n) " create_venv
if [[ $create_venv == "y" || $create_venv == "Y" ]]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo "Activate the virtual environment with:"
    echo -e "${YELLOW}source venv/bin/activate${NC}"
    echo "Then run this script again."
    exit 0
fi

# Make run script executable
chmod +x scripts/run_strategy.py

# Confirm successful installation
echo -e "${GREEN}Adaptive Market Making Strategy setup complete!${NC}"
echo ""
echo "To run the strategy:"
echo -e "${YELLOW}./scripts/run_strategy.py --config conf/adaptive_market_making_config.yml${NC}"
echo ""
echo "Make sure your Hummingbot instance is running and properly configured."
echo "Edit conf/adaptive_market_making_config.yml to customize strategy parameters." 