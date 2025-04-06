#!/bin/bash

# Helper script to set up and run Precision Trading Strategy
# This script automatically detects the current location of Hummingbot

# Get the absolute path of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# The script is assumed to be in the hummingbot root directory
HUMMINGBOT_ROOT="$SCRIPT_DIR"
HUMMINGBOT_DIR="$HUMMINGBOT_ROOT/hummingbot"

echo "=== Precision Trading Strategy Setup ==="
echo "Detected Hummingbot at: $HUMMINGBOT_ROOT"

# Check if script files exist
STRATEGY_SCRIPT="$HUMMINGBOT_DIR/scripts/precision_trading.py"
CONFIG_SCRIPT="$HUMMINGBOT_DIR/conf/strategies/precision_trading_config.py"

if [ ! -f "$STRATEGY_SCRIPT" ]; then
    echo "Error: Strategy script not found at $STRATEGY_SCRIPT"
    exit 1
fi

if [ ! -f "$CONFIG_SCRIPT" ]; then
    echo "Error: Config script not found at $CONFIG_SCRIPT"
    exit 1
fi

echo "Found strategy files:"
echo "  - $STRATEGY_SCRIPT"
echo "  - $CONFIG_SCRIPT"
echo ""

# Instructions for using the strategy
echo "To use the Precision Trading Strategy:"
echo "1. Start Hummingbot:"
echo "   cd $HUMMINGBOT_DIR"
echo "   conda activate hummingbot"
echo "   bin/hummingbot.py"
echo ""
echo "2. In the Hummingbot client, run:"
echo "   import precision_trading_config"
echo "   create --script-config precision_trading_config"
echo "   start --script precision_trading.py --conf your_config_name"
echo ""
echo "This strategy will work regardless of where you move the hummingbot folder."

# Optionally, you can add code here to automatically start Hummingbot
# if [ "$1" == "--start" ]; then
#    cd "$HUMMINGBOT_DIR"
#    # This assumes conda is properly set up in your environment
#    conda activate hummingbot
#    bin/hummingbot.py
# fi 