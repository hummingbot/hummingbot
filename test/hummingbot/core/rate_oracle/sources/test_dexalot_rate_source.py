import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS, dexalot_web_utils as web_utils
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.dexalot_rate_source import DexalotRateSource
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory

# Override the async_ttl_cache decorator to be a no-op.
# def async_ttl_cache(ttl: int = 3600, maxsize: int = 1):
#     def decorator(fn):
#         return fn
#
#     return decorator


class DexalotRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "ALOT"
        cls.global_token = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def setUp(self):
        super().setUp()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await ConnectionsFactory().close()
        self.factory = ConnectionsFactory()
        self.mocking_assistant = NetworkMockingAssistant("__this_is_not_a_loop__")
        await self.mocking_assistant.async_init()

    async def asyncTearDown(self) -> None:
        await self.factory.close()
        await super().asyncTearDown()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def setup_dexalot_responses(self, ws_connect_mock, mock_api, rate_source):
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
        prices = await rate_source.get_prices()

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        return prices

    @aioresponses()
    async def test_get_prices(self, mock_api):
        expected_rate = Decimal("10")
        rate_source = DexalotRateSource()
        prices = await self.setup_dexalot_responses(mock_api=mock_api, rate_source=rate_source)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)
