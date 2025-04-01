import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.coin_gecko_rate_source import CoinGeckoRateSource
from hummingbot.data_feed.coin_gecko_data_feed import coin_gecko_constants as CONSTANTS
from hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_constants import COOLOFF_AFTER_BAN


class CoinGeckoRateSourceTest(IsolatedAsyncioWrapperTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.extra_token = "EXTRA"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.extra_trading_pair = combine_to_hb_trading_pair(base=cls.extra_token, quote=cls.global_token)

    def get_coin_markets_data_mock(self, price: float):
        data = [
            {
                "id": self.target_token.lower(),
                "symbol": self.target_token.lower(),
                "name": self.target_token.title(),
                "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png?1547033579",
                "current_price": price,
                "market_cap": 451469235435,
                "market_cap_rank": 1,
                "fully_diluted_valuation": 496425271642,
                "total_volume": 50599610665,
                "high_24h": 23655,
                "low_24h": 21746,
                "price_change_24h": 1640.38,
                "price_change_percentage_24h": 7.45665,
                "market_cap_change_24h": 31187048611,
                "market_cap_change_percentage_24h": 7.4205,
                "circulating_supply": 19098250,
                "total_supply": 21000000,
                "max_supply": 21000000,
                "ath": 69045,
                "ath_change_percentage": -65.90618,
                "ath_date": "2021-11-10T14:24:11.849Z",
                "atl": 67.81,
                "atl_change_percentage": 34615.15839,
                "atl_date": "2013-07-06T00:00:00.000Z",
                "roi": None,
                "last_updated": "2022-07-20T06:30:40.123Z"
            },
        ]
        return data

    def get_extra_token_data_mock(self, price: float):
        data = [
            {
                "id": self.extra_token.lower(),
                "symbol": self.extra_token.lower(),
                "name": self.extra_token.title(),
                "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png?1547033579",
                "current_price": price,
                "market_cap": 451469235435,
                "market_cap_rank": 1,
                "fully_diluted_valuation": 496425271642,
                "total_volume": 50599610665,
                "high_24h": 23655,
                "low_24h": 21746,
                "price_change_24h": 1640.38,
                "price_change_percentage_24h": 7.45665,
                "market_cap_change_24h": 31187048611,
                "market_cap_change_percentage_24h": 7.4205,
                "circulating_supply": 19098250,
                "total_supply": 21000000,
                "max_supply": 21000000,
                "ath": 69045,
                "ath_change_percentage": -65.90618,
                "ath_date": "2021-11-10T14:24:11.849Z",
                "atl": 67.81,
                "atl_change_percentage": 34615.15839,
                "atl_date": "2013-07-06T00:00:00.000Z",
                "roi": None,
                "last_updated": "2022-07-20T06:30:40.123Z"
            },
        ]
        return data

    @staticmethod
    def get_prices_by_page_url(page_no, vs_currency):
        url = (
            f"{CONSTANTS.BASE_URL}{CONSTANTS.PRICES_REST_ENDPOINT}"
            f"?order=market_cap_desc&page={page_no}"
            f"&per_page=250&sparkline=false&vs_currency={vs_currency}"
        )
        return url

    @staticmethod
    def get_prices_by_page_with_category_url(category, page_no, vs_currency):
        url = (
            f"{CONSTANTS.BASE_URL}{CONSTANTS.PRICES_REST_ENDPOINT}"
            f"?category={category}&order=market_cap_desc&page={page_no}"
            f"&per_page=250&sparkline=false&vs_currency={vs_currency}"
        )
        return url

    def setup_responses(self, mock_api: aioresponses, expected_rate: Decimal):
        # setup supported tokens response
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        data = [self.global_token.lower(), self.extra_token.lower()]
        mock_api.get(url=url, body=json.dumps(data))

        # setup prices by page responses
        initial_data_set = False
        for page_no in range(1, 11):
            url = self.get_prices_by_page_url(page_no=page_no, vs_currency=self.global_token.lower())
            data = self.get_coin_markets_data_mock(price=float(expected_rate)) if not initial_data_set else []
            initial_data_set = True
            mock_api.get(url=url, body=json.dumps(data))

        # setup prices by page with category responses
        initial_data_set = False
        for page_no in range(1, 3):
            for category in CONSTANTS.TOKEN_CATEGORIES:
                url = self.get_prices_by_page_with_category_url(
                    category=category, page_no=page_no, vs_currency=self.global_token.lower()
                )
                data = self.get_coin_markets_data_mock(price=float(expected_rate)) if not initial_data_set else []
                initial_data_set = True
                mock_api.get(url=url, body=json.dumps(data))

        # setup extra token price response
        url = (
            f"{CONSTANTS.BASE_URL}{CONSTANTS.PRICES_REST_ENDPOINT}"
            f"?ids={self.extra_token.lower()}&vs_currency={self.global_token.lower()}"
        )
        data = self.get_extra_token_data_mock(price=20.0)
        mock_api.get(url=url, body=json.dumps(data))

    def setup_responses_with_exception(self, mock_api: aioresponses, expected_rate: Decimal, exception=Exception):
        # setup supported tokens response
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        data = [self.global_token.lower(), self.extra_token.lower()]
        mock_api.get(url=url, body=json.dumps(data))

        # setup prices by page responses
        initial_data_set = False
        for page_no in range(1, 11):
            url = self.get_prices_by_page_url(page_no=page_no, vs_currency=self.global_token.lower())
            data = self.get_coin_markets_data_mock(price=float(expected_rate)) if not initial_data_set else []
            initial_data_set = True
            if page_no == 7:
                mock_api.get(url=url, body=None, exception=exception)
            else:
                mock_api.get(url=url, body=json.dumps(data))

        # setup prices by page with category responses
        initial_data_set = False
        for page_no in range(1, 3):
            for category in CONSTANTS.TOKEN_CATEGORIES:
                url = self.get_prices_by_page_with_category_url(
                    category=category, page_no=page_no, vs_currency=self.global_token.lower()
                )
                data = self.get_coin_markets_data_mock(price=float(expected_rate)) if not initial_data_set else []
                initial_data_set = True

                # We want to test the IOError that does nothing and 'finally' to a asyncio.sleep()
                # So first test the IOError, then follow with Exception that gets out of the loop - M. Clunky strikes again
                if page_no == 1:
                    mock_api.get(url=url, body=None, exception=exception)
                elif page_no == 2:
                    mock_api.get(url=url, body=None, exception=Exception)
                else:
                    mock_api.get(url=url, body=json.dumps(data))

        # setup extra token price response
        url = (
            f"{CONSTANTS.BASE_URL}{CONSTANTS.PRICES_REST_ENDPOINT}"
            f"?ids={self.extra_token.lower()}&vs_currency={self.global_token.lower()}"
        )
        data = self.get_extra_token_data_mock(price=20.0)
        mock_api.get(url=url, body=json.dumps(data))

    @aioresponses()
    async def test_get_prices_no_extra_tokens(self, mock_api: aioresponses):
        print("test_get_prices_no_extra_tokens() - mock_api.responses", mock_api)
        expected_rate = Decimal("10")
        self.setup_responses(mock_api=mock_api, expected_rate=expected_rate)
        print(mock_api.requests)

        rate_source = CoinGeckoRateSource(extra_token_ids=[])

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertNotIn(self.extra_trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    @aioresponses()
    async def test_get_prices_with_extra_tokens(self, mock_api: aioresponses):
        expected_rate = Decimal("10")
        self.setup_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = CoinGeckoRateSource(extra_token_ids=[self.extra_token])

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertIn(self.extra_trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    @aioresponses()
    async def test_get_prices_raises_IOError_cooloff(self, mock_api: aioresponses):
        # setup supported tokens response
        expected_rate = Decimal("10")
        # IOError exception on page 7 (hardcoded to page 7
        self.setup_responses_with_exception(mock_api=mock_api, expected_rate=expected_rate, exception=IOError)

        rate_source = CoinGeckoRateSource(extra_token_ids=[])

        # The test creates a response with an exception, but the exception is caught and the code continues
        # So we need to test that the code continues and the prices are returned, but for the particular page
        # that the exception was raised, the prices are not returned and the mocked API returns ClientConnectionError
        with patch.object(CoinGeckoRateSource, "_sleep", new_callable=AsyncMock) as mock_sleep:
            with self.assertRaises(Exception) as e:
                await rate_source.get_prices(quote_token=self.global_token)
            self.assertIn("page=7", e.exception.args[0])
            # Exception is caught and the code continues, so the sleep is called
            mock_sleep.assert_called_with(COOLOFF_AFTER_BAN)
            mock_sleep.assert_awaited()

    @aioresponses()
    def test_get_prices_raises_non_IOError_no_cooloff(self, mock_api: aioresponses):
        # setup supported tokens response
        expected_rate = Decimal("10")
        # IOError exception on page 7 (hardcoded to page 7
        self.setup_responses_with_exception(mock_api=mock_api, expected_rate=expected_rate, exception=Exception)

        rate_source = CoinGeckoRateSource(extra_token_ids=[])

        # The test creates a response with an exception, but the exception is caught and the code continues
        # So we need to test that the code continues and the prices are returned, but for the particular page
        # that the exception was raised, the prices are not returned and the mocked API returns ClientConnectionError
        with patch.object(CoinGeckoRateSource, "_sleep", new_callable=AsyncMock) as mock_sleep:
            # The exception is not an IOError, so the code does not sleep
            with self.assertRaises(Exception) as e:
                self.run_async_with_timeout(rate_source.get_prices(quote_token=self.global_token))
            self.assertIn("Unhandled error in CoinGecko rate source", e.exception.args[0])
            # Exception is caught and the code continues, so the sleep is called
            mock_sleep.assert_not_called()
