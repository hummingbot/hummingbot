import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS, dexalot_web_utils as web_utils
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.dexalot_rate_source import DexalotRateSource


class DexalotRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "ALOT"
        cls.global_token = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")
        cls.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def setup_dexalot_responses(self, ws_connect_mock, mock_api, rate_source):
        symbols_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        symbols_response = [
            {'env': 'production-multi-subnet', 'pair': 'ALOT/USDC', 'base': 'ALOT', 'quote': 'USDC',
             'basedisplaydecimals': 2,
             'quotedisplaydecimals': 4,
             'baseaddress': '0x093783055F9047C2BfF99c4e414501F8A147bC69',  # noqa: mock
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 20, 'additional_ordertypes': None, 'taker_fee': 0.001, 'maker_fee': 0.0012},
            {'env': 'production-multi-subnet', 'pair': self.ignored_trading_pair, 'base': 'SOME', 'quote': 'PAIR',
             'basedisplaydecimals': 2,
             'quotedisplaydecimals': 4,
             'baseaddress': '0x093783055F9047C2BfF99c4e414501F8A147bC69',  # noqa: mock
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 20, 'additional_ordertypes': None, 'taker_fee': 0.001, 'maker_fee': 0.0012},

            {
                "id": self.ignored_trading_pair,
                "base": "SOME",
                "quote": "PAIR",
                "fee": "0.2",
                "trade_status": "non-tradable",
            }

        ]
        mock_api.get(url=symbols_url, body=json.dumps(symbols_response))
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe = {'data': [
            {'pair': 'EURC/USDC', 'date': '2024-10-04T08:54:32.021Z', 'low': '1.0973', 'high': '1.1042',
             'open': '1.104082', 'close': '1.0985', 'volume': '202943.428252', 'quote_volume': '223745.305841618516',
             'change': '-0.0051'},
            {'pair': 'ALOT/USDC', 'date': '2024-10-04T08:54:32.021Z', 'low': '9', 'high': '11',
             'open': '0.56628', 'close': '0.5659', 'volume': '124062.5422952677657237',
             'quote_volume': '70336.660027130678322247184899', 'change': '-0.0007'},
            {'pair': 'WBTC/USDC', 'date': '2024-10-04T08:54:32.021Z', 'low': '60736.084907', 'high': '62315',
             'open': '61466.985162', 'close': '61985.1', 'volume': '28.4564045',
             'quote_volume': '1753078.71879646658951', 'change': '0.0084'}], 'type': 'marketSnapShot'}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe))
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        return prices

    @aioresponses()
    def test_get_prices(self, mock_api):
        expected_rate = Decimal("10")
        rate_source = DexalotRateSource()
        prices = self.setup_dexalot_responses(mock_api=mock_api, rate_source=rate_source)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)
