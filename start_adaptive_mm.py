#!/usr/bin/env python3

import asyncio
import logging
from typing import Dict, List

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.settings import STRATEGIES_CONF_DIR_PATH

async def main():
    try:
        read_system_configs_from_yml()
        
        # Set up paper trading mode
        global_config_map["paper_trade_enabled"].value = True
        
        hummingbot = HummingbotApplication.main_application()
        await hummingbot.start(script="adaptive_market_making_enhanced.py")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logging.error("Error running bot: %s", str(e))
        raise

if __name__ == "__main__":
    asyncio.run(main())
