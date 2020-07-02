#!/usr/bin/env python
from hummingbot.market.kraken.kraken_market import KrakenMarket
import asyncio
import aiohttp
import logging
from typing import (
    Optional,
    List,
    Dict,
    Any,
)
import unittest

ASSET_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"

class KrakenTradingPairsUnitTest(unittest.TestCase):
    asset_pairs: Dict[str, Any] = {}
    
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        print("Initializing Kraken market...")
        cls.ev_loop.run_until_complete(cls.fetch())
        print("Ready.")
        
    @classmethod
    async def fetch(cls):
        client = aiohttp.ClientSession()
        asset_pairs_response = await client.get(ASSET_PAIRS_URL)
        asset_pairs_data: Dict[str, Any] = await asset_pairs_response.json()
        cls.asset_pairs: Dict[str, Any] = asset_pairs_data["result"] 

    def test_trading_pair_conversion(self):
        for asset_pair in self.asset_pairs:
            from_kraken = KrakenMarket.convert_from_exchange_trading_pair(asset_pair)
            to_kraken = KrakenMarket.convert_to_exchange_trading_pair(from_kraken)
            self.assertEqual(asset_pair, to_kraken)

def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()

if __name__ == "__main__":
    main()