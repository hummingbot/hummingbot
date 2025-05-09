import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.coin_cap_rate_source import CoinCapRateSource
from hummingbot.data_feed.coin_cap_data_feed import coin_cap_constants as CONSTANTS


class CoinCapRateSourceTest(IsolatedAsyncioWrapperTestCase):
    level = 0
    target_token: str
    target_asset_id: str
    global_token: str
    trading_pair: str

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.target_asset_id = "some CoinAlpha ID"
        cls.global_token = CONSTANTS.UNIVERSAL_QUOTE_TOKEN
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.rate_source = CoinCapRateSource(assets_map={}, api_key="")
        self.rate_source._coin_cap_data_feed.logger().setLevel(1)
        self.rate_source._coin_cap_data_feed.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        await self.mocking_assistant.async_init()
        self.rate_source._coin_cap_data_feed._get_api_factory()
        self._web_socket_mock = self.mocking_assistant.configure_web_assistants_factory(
            web_assistants_factory=self.rate_source._coin_cap_data_feed._api_factory
        )

    def handle(self, record):
        self.log_records.append(record)

    def get_coin_cap_assets_data_mock(
        self,
        asset_symbol: str,
        asset_price: Decimal,
        asset_id: Optional[str] = None,
    ):
        data = {
            "data": [
                {
                    "id": asset_id or self.target_asset_id,
                    "rank": "1",
                    "symbol": asset_symbol,
                    "name": "Bitcoin",
                    "supply": "19351375.0000000000000000",
                    "maxSupply": "21000000.0000000000000000",
                    "marketCapUsd": "560124156928.7894433300126125",
                    "volumeUsd24Hr": "8809682089.3591086933779149",
                    "priceUsd": str(asset_price),
                    "changePercent24Hr": "-3.7368339984395858",
                    "vwap24Hr": "29321.6954689987292113",
                    "explorer": "https://blockchain.info/",
                },
                {
                    "id": "bitcoin-bep2",
                    "rank": "36",
                    "symbol": "BTCB",
                    "name": "Bitcoin BEP2",
                    "supply": "53076.5813160500000000",
                    "maxSupply": None,
                    "marketCapUsd": "1535042933.7400446414478907",
                    "volumeUsd24Hr": "545107668.1789385958198549",
                    "priceUsd": "28921.2849749962704851",
                    "changePercent24Hr": "-3.6734367191141411",
                    "vwap24Hr": "29306.9911285134523131",
                    "explorer": "https://explorer.binance.org/asset/BTCB-1DE",
                },
            ],
            "timestamp": 1681975911184,
        }
        return data

    @aioresponses()
    async def test_get_prices(self, mock_api: aioresponses):
        expected_rate = Decimal("20")

        data = self.get_coin_cap_assets_data_mock(asset_symbol=self.target_token, asset_price=expected_rate)
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.ALL_ASSETS_ENDPOINT}"
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(
            url=url_regex,
            body=json.dumps(data),
            headers={
                "X-Ratelimit-Remaining": str(CONSTANTS.NO_KEY_LIMIT - 1),
                "X-Ratelimit-Limit": str(CONSTANTS.NO_KEY_LIMIT),
            },
        )

        prices = await self.rate_source.get_prices(quote_token="SOMETOKEN")

        self.assertEqual(prices, {})

        prices = await self.rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    @aioresponses()
    async def test_check_network(self, mock_api: aioresponses):
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.HEALTH_CHECK_ENDPOINT}"
        mock_api.get(url, exception=Exception())

        status = await self.rate_source.check_network()
        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

        mock_api.get(
            url,
            body=json.dumps({}),
            headers={
                "X-Ratelimit-Remaining": str(CONSTANTS.NO_KEY_LIMIT - 1),
                "X-Ratelimit-Limit": str(CONSTANTS.NO_KEY_LIMIT),
            },
        )

        status = await self.rate_source.check_network()
        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    async def test_ws_stream_prices(self, mock_api: aioresponses):
        # initial request
        rest_rate = Decimal("20")
        data = self.get_coin_cap_assets_data_mock(asset_symbol=self.target_token, asset_price=rest_rate)
        assets_map = {
            asset_data["symbol"]: asset_data["id"] for asset_data in data["data"]
        }
        rate_source = CoinCapRateSource(assets_map=assets_map, api_key="")
        rate_source._coin_cap_data_feed._get_api_factory()
        web_socket_mock = self.mocking_assistant.configure_web_assistants_factory(
            web_assistants_factory=rate_source._coin_cap_data_feed._api_factory
        )
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.ALL_ASSETS_ENDPOINT}"
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(
            url=url_regex,
            body=json.dumps(data),
            headers={
                "X-Ratelimit-Remaining": str(CONSTANTS.NO_KEY_LIMIT - 1),
                "X-Ratelimit-Limit": str(CONSTANTS.NO_KEY_LIMIT),
            },
            repeat=True,
        )

        await rate_source.start_network()

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(rest_rate, prices[self.trading_pair])

        streamed_rate = rest_rate + Decimal("1")
        stream_response = {self.target_asset_id: str(streamed_rate)}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=web_socket_mock, message=json.dumps(stream_response)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=web_socket_mock)

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(streamed_rate, prices[self.trading_pair])

        await rate_source.stop_network()

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(rest_rate, prices[self.trading_pair])  # rest requests are used once again

    @aioresponses()
    @patch("hummingbot.data_feed.coin_cap_data_feed.coin_cap_data_feed.CoinCapDataFeed._sleep")
    async def test_ws_stream_logs_exceptions_and_restarts(self, mock_api: aioresponses, sleep_mock: AsyncMock):
        continue_event = asyncio.Event()

        async def _continue_event_wait(*_, **__):
            await continue_event.wait()
            continue_event.clear()

        sleep_mock.side_effect = _continue_event_wait

        # initial request
        rest_rate = Decimal("20")
        data = self.get_coin_cap_assets_data_mock(asset_symbol=self.target_token, asset_price=rest_rate)
        assets_map = {
            asset_data["symbol"]: asset_data["id"] for asset_data in data["data"]
        }
        rate_source = CoinCapRateSource(assets_map=assets_map, api_key="")
        rate_source._coin_cap_data_feed._get_api_factory()
        web_socket_mock = self.mocking_assistant.configure_web_assistants_factory(
            web_assistants_factory=rate_source._coin_cap_data_feed._api_factory
        )
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.ALL_ASSETS_ENDPOINT}"
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(
            url=url_regex,
            body=json.dumps(data),
            headers={
                "X-Ratelimit-Remaining": str(CONSTANTS.NO_KEY_LIMIT - 1),
                "X-Ratelimit-Limit": str(CONSTANTS.NO_KEY_LIMIT),
            },
            repeat=True,
        )

        await rate_source.start_network()

        streamed_rate = rest_rate + Decimal("1")
        stream_response = {self.target_asset_id: str(streamed_rate)}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=web_socket_mock, message=json.dumps(stream_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_exception(
            websocket_mock=web_socket_mock, exception=Exception("test exception")
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=web_socket_mock)

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(streamed_rate, prices[self.trading_pair])
        log_level = "NETWORK"
        message = "Unexpected error while streaming prices. Restarting the stream."
        any(
            record.levelname == log_level and message == record.getMessage() is not None
            for record in self.log_records
        )

        streamed_rate = rest_rate + Decimal("2")
        stream_response = {self.target_asset_id: str(streamed_rate)}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=web_socket_mock, message=json.dumps(stream_response)
        )

        continue_event.set()

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=web_socket_mock)

        prices = await rate_source.get_prices(quote_token=self.global_token)

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(streamed_rate, prices[self.trading_pair])
