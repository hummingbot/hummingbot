import sys
import asyncio
import unittest
import aiohttp
import logging
from os.path import join, realpath
from typing import Dict, Any

from hummingbot.connector.exchange.hitbtc.hitbtc_api_order_book_data_source import HitbtcAPIOrderBookDataSource
from hummingbot.connector.exchange.hitbtc.hitbtc_constants import Constants
from hummingbot.connector.exchange.hitbtc.hitbtc_utils import aiohttp_response_with_errors
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

    async def fetch_symbols(self) -> Dict[Any, Any]:
        endpoint = Constants.ENDPOINT['SYMBOL']
        http_client = aiohttp.ClientSession()
        http_status, response, request_errors = await aiohttp_response_with_errors(http_client.request(method='GET',
                                                                                                       url=f"{Constants.REST_URL}/{endpoint}"))
        await http_client.close()
        return response

    def test_all_trading_pairs_matched(self):
        result = self.ev_loop.run_until_complete(self.fetch_symbols())
        print('')
        pairs = [i['id'] for i in result]
        unmatched_pairs = []
        for pair in pairs:
            matched_pair = asyncio.get_event_loop().run_until_complete(
                HitbtcAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(pair))
            if matched_pair is None:
                matched_pair_split = None
                print(f"\nUnmatched pair: {pair}\n")
                unmatched_pairs.append(pair)
            else:
                matched_pair_split = matched_pair.split('-')
            if 'USDUSD' in pair or ('USD' in matched_pair_split[0] and 'USD' in matched_pair_split[1]):
                print(f'Found double USD pair: `{pair}` matched to => `{matched_pair}`')
        assert len(unmatched_pairs) == 0
