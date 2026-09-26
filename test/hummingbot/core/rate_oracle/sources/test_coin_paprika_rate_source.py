import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List, Optional

from aioresponses import aioresponses

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.coin_paprika_rate_source import CoinPaprikaRateSource
from hummingbot.data_feed.coin_paprika_data_feed import coin_paprika_constants as CONSTANTS


class CoinPaprikaRateSourceTest(IsolatedAsyncioWrapperTestCase):
    level = 0
    target_token: str
    target_asset_id: str
    global_token: str
    trading_pair: str

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.target_asset_id = "coinalpha-coinalpha"
        cls.global_token = CONSTANTS.UNIVERSAL_QUOTE_TOKEN
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.rate_source = CoinPaprikaRateSource()
        self.rate_source.get_prices.cache_clear()  # the TTL cache is shared at the class level
        self.rate_source.logger().setLevel(1)
        self.rate_source.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def get_coin_paprika_ticker_data_mock(
        self,
        asset_symbol: str,
        asset_price: Decimal,
        quote_token: str,
        rank: int = 2,
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = {
            "id": asset_id or self.target_asset_id,
            "name": "CoinAlpha",
            "symbol": asset_symbol,
            "rank": rank,
            "total_supply": 20057419,
            "max_supply": 21000000,
            "beta_value": 0.982312,
            "first_data_at": "2010-07-17T00:00:00Z",
            "last_updated": "2026-07-17T06:51:16Z",
            "quotes": {
                quote_token: {
                    "price": float(asset_price),
                    "volume_24h": 25060010126.46113,
                    "volume_24h_change_24h": 10.15,
                    "market_cap": 1260652589126,
                    "market_cap_change_24h": -2.03,
                    "percent_change_24h": -2.03,
                    "ath_price": 126173.1777846797,
                    "ath_date": "2025-10-06T19:00:40Z",
                    "percent_from_price_ath": -50.21,
                },
            },
        }
        return data

    def get_coin_paprika_tickers_data_mock(
        self, asset_symbol: str, asset_price: Decimal, quote_token: str
    ) -> List[Dict[str, Any]]:
        data = [
            # a lower-ranked coin that shares its symbol with the target coin and is returned first
            self.get_coin_paprika_ticker_data_mock(
                asset_symbol=asset_symbol,
                asset_price=asset_price + Decimal("1"),
                quote_token=quote_token,
                rank=36,
                asset_id="coinalpha2-coinalpha-two",
            ),
            self.get_coin_paprika_ticker_data_mock(
                asset_symbol=asset_symbol, asset_price=asset_price, quote_token=quote_token
            ),
            # a coin without a price, which should not be included in the results
            self.get_coin_paprika_ticker_data_mock(
                asset_symbol="SOMEDEADCOIN",
                asset_price=Decimal("0"),
                quote_token=quote_token,
                rank=2000,
                asset_id="somedeadcoin-some-dead-coin",
            ),
        ]
        return data

    def setup_all_tickers_response(
        self, mock_api: aioresponses, asset_price: Decimal, quote_token: str
    ):
        data = self.get_coin_paprika_tickers_data_mock(
            asset_symbol=self.target_token, asset_price=asset_price, quote_token=quote_token
        )
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.ALL_TICKERS_ENDPOINT}"
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(url=url_regex, body=json.dumps(data))

    @aioresponses()
    async def test_get_prices(self, mock_api: aioresponses):
        expected_rate = Decimal("20")
        self.setup_all_tickers_response(mock_api=mock_api, asset_price=expected_rate, quote_token=self.global_token)

        prices = await self.rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

        # the higher-ranked coin wins when two coins share a symbol
        self.assertNotEqual(expected_rate + Decimal("1"), prices[self.trading_pair])

        # coins without a price are skipped
        dead_coin_pair = combine_to_hb_trading_pair(base="SOMEDEADCOIN", quote=self.global_token)
        self.assertNotIn(dead_coin_pair, prices)

    @aioresponses()
    async def test_get_prices_with_supported_non_usd_quote_token(self, mock_api: aioresponses):
        expected_rate = Decimal("20")
        quote_token = "EUR"
        self.setup_all_tickers_response(mock_api=mock_api, asset_price=expected_rate, quote_token=quote_token)

        prices = await self.rate_source.get_prices(quote_token=quote_token)

        trading_pair = combine_to_hb_trading_pair(base=self.target_token, quote=quote_token)
        self.assertIn(trading_pair, prices)
        self.assertEqual(expected_rate, prices[trading_pair])

    @aioresponses()
    async def test_get_prices_falls_back_to_usd_for_unsupported_quote_token(self, mock_api: aioresponses):
        expected_rate = Decimal("20")
        self.setup_all_tickers_response(mock_api=mock_api, asset_price=expected_rate, quote_token=self.global_token)

        prices = await self.rate_source.get_prices(quote_token="SOMETOKEN")

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertTrue(
            self._is_logged(
                log_level="WARNING",
                message=(
                    "CoinPaprikaRateSource does not support SOMETOKEN as the quote token."
                    f" Using {CONSTANTS.UNIVERSAL_QUOTE_TOKEN} quotes instead."
                ),
            )
        )

    @aioresponses()
    async def test_get_prices_without_quote_token_defaults_to_usd(self, mock_api: aioresponses):
        expected_rate = Decimal("20")
        self.setup_all_tickers_response(mock_api=mock_api, asset_price=expected_rate, quote_token=self.global_token)

        prices = await self.rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    @aioresponses()
    async def test_check_network(self, mock_api: aioresponses):
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.HEALTH_CHECK_ENDPOINT}"
        mock_api.get(url, exception=Exception())

        status = await self.rate_source.check_network()
        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

        data = self.get_coin_paprika_ticker_data_mock(
            asset_symbol="BTC", asset_price=Decimal("62852.17"), quote_token=self.global_token, rank=1
        )
        mock_api.get(url, body=json.dumps(data))

        status = await self.rate_source.check_network()
        self.assertEqual(NetworkStatus.CONNECTED, status)

    async def test_start_and_stop_network(self):
        await self.rate_source.start_network()
        await self.rate_source.stop_network()

    def test_name(self):
        self.assertEqual("coin_paprika", self.rate_source.name)
        self.assertEqual("coin_paprika_api", self.rate_source._coin_paprika_data_feed.name)
        self.assertEqual(
            CONSTANTS.UNIVERSAL_QUOTE_TOKEN, self.rate_source._coin_paprika_data_feed.universal_quote_token
        )
