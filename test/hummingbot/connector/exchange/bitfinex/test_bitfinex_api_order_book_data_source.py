import asyncio
import json
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

import hummingbot.connector.exchange.bitfinex.bitfinex_utils as utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitfinex import BITFINEX_REST_URL
from hummingbot.connector.exchange.bitfinex.bitfinex_api_order_book_data_source import BitfinexAPIOrderBookDataSource
from hummingbot.connector.exchange.bitfinex.bitfinex_exchange import BitfinexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class BitfinexAPIOrderBookDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        BitfinexAPIOrderBookDataSource.logger().setLevel(1)
        BitfinexAPIOrderBookDataSource.logger().addHandler(self)
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitfinexExchange(
            client_config_map=client_config_map,
            bitfinex_api_key="",
            bitfinex_secret_key="",
            trading_pairs=[],
            trading_required=False)

        self.data_source = BitfinexAPIOrderBookDataSource(trading_pairs=[self.trading_pair])

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    @aioresponses()
    def test_get_last_traded_price(self, api_mock):
        response = [
            10645,
            73.93854271,
            10647,
            75.22266119,
            731.60645389,
            0.0738,
            10644.00645389,
            14480.89849423,
            10766,
            9889.1449809]
        api_mock.get(f"{BITFINEX_REST_URL}/ticker/{utils.convert_to_exchange_trading_pair('BTC-USDT')}",
                     body=json.dumps(response))
        last_price = asyncio.get_event_loop().run_until_complete(
            BitfinexAPIOrderBookDataSource.get_last_traded_price("BTC-USDT"))

        self.assertEqual(response[6], last_price)

    @aioresponses()
    def test_get_last_traded_price_returns_zero_when_an_error_happens(self, api_mock):
        response = {"error": "ERR_RATE_LIMIT"}
        api_mock.get(f"{BITFINEX_REST_URL}/ticker/{utils.convert_to_exchange_trading_pair('BTC-USDT')}",
                     body=json.dumps(response))
        last_price = asyncio.get_event_loop().run_until_complete(
            BitfinexAPIOrderBookDataSource.get_last_traded_price("BTC-USDT"))

        self.assertEqual(0, last_price)
        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error encountered requesting ticker information. The response was: {response} "
            f"(There was an error requesting ticker information BTC-USDT ({response}))"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "result": None,
            "id": 1
        }
        result_subscribe_diffs = {
            "result": None,
            "id": 2
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "method": "SUBSCRIBE",
            "params": [f"{self.ex_trading_pair.lower()}@trade"],
            "id": 1}
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "method": "SUBSCRIBE",
            "params": [f"{self.ex_trading_pair.lower()}@depth@100ms"],
            "id": 2}
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))
