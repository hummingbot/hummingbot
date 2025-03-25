import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.kucoin_rate_source import KucoinRateSource


class KucoinRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def setup_kucoin_responses(self, mock_api, expected_rate: Decimal):
        symbols_url = f"{CONSTANTS.BASE_PATH_URL['main']}{CONSTANTS.SYMBOLS_PATH_URL}"
        symbols_response = {  # truncated response
            "data": [
                {
                    "symbol": self.trading_pair,
                    "baseCurrency": self.target_token,
                    "quoteCurrency": self.global_token,
                    "enableTrading": True,
                },
                {
                    "symbol": self.ignored_trading_pair,
                    "baseCurrency": "SOME",
                    "quoteCurrency": "PAIR",
                    "enableTrading": False,
                },
            ],
        }
        mock_api.get(url=symbols_url, body=json.dumps(symbols_response))
        prices_url = f"{CONSTANTS.BASE_PATH_URL['main']}{CONSTANTS.ALL_TICKERS_PATH_URL}"
        prices_response = {  # truncated response
            "data": {
                "time": 1602832092060,
                "ticker": [
                    {
                        "symbol": self.trading_pair,
                        "symbolName": self.trading_pair,
                        "buy": str(expected_rate - Decimal("0.1")),
                        "sell": str(expected_rate + Decimal("0.1")),
                    },
                    {
                        "symbol": self.ignored_trading_pair,
                        "symbolName": self.ignored_trading_pair,
                        "buy": str(expected_rate - Decimal("0.1")),
                        "sell": str(expected_rate + Decimal("0.1")),
                    }
                ],
            },
        }
        mock_api.get(url=prices_url, body=json.dumps(prices_response))

    @aioresponses()
    async def test_get_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_kucoin_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = KucoinRateSource()
        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)
