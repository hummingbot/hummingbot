import asyncio
import pandas as pd
import time
import unittest

from typing import Any
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.core.event.events import PositionMode


class BybitPerpetualDerivativeUnitTests(unittest.TestCase):
    # The level is required to receive logs from the connector logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.api_responses = asyncio.Queue()
        self.log_records = []

        self.connector = BybitPerpetualDerivative(
            bybit_perpetual_api_key="TEST_KEY",
            bybit_perpetual_secret_key="SECRET_KEY",
            trading_pairs=[self.trading_pair],
            domain="bybit_testnet"
        )
        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        self.connector_task = None

    def tearDown(self) -> None:
        super().tearDown()
        self.connector_task and self.connector_task.cancel()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    async def _get_next_api_response(self):
        message = await self.api_responses.get()
        return message

    def _set_mock_response(self, mock_api, status: int, json_data: Any, text_data: str = ""):
        self.api_responses.put_nowait(json_data)
        mock_api.return_value.status = status
        mock_api.return_value.json.side_effect = self._get_next_api_response
        mock_api.return_value.text = AsyncMock(return_value=text_data)

    def test_aiohttp_client(self):
        self.assertIsNone(self.connector._shared_client)
        self.ev_loop.run_until_complete(self.connector._aiohttp_client())
        self.assertIsNotNone(self.connector._shared_client)

    def test_supported_position_modes(self):
        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, self.connector.supported_position_modes())

    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_next_funding_timestamp")
    def test_tick_funding_fee_poll_notifier_set(self, mock_time):
        mock_time.return_value = pd.Timestamp("2021-08-21-01:00:00", tz="UTC").timestamp()

        self.assertFalse(self.connector._funding_fee_poll_notifier.is_set())
        self.connector.tick(int(time.time()))
        self.assertTrue(self.connector._funding_fee_poll_notifier.is_set())

    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source.BybitPerpetualAPIOrderBookDataSource.trading_pair_symbol_map", new_callable=AsyncMock)
    def test_fetch_funding_fee_unsupported_trading_pair(self, mock_symbol_map):
        mock_symbol_map.return_value = {
            self.ex_trading_pair: self.trading_pair
        }

        # Test 1: Unsupported trading pair
        self.connector_task = self.ev_loop.create_task(
            self.connector._fetch_funding_fee("UNSUPPORTED-PAIR")
        )
        result = self.ev_loop.run_until_complete(self.connector_task)
        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("ERROR", "Unable to fetch funding fee for UNSUPPORTED-PAIR. Trading pair not supported.")
        )

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source.BybitPerpetualAPIOrderBookDataSource.trading_pair_symbol_map", new_callable=AsyncMock)
    def test_fetch_funding_fee_supported_trading_pair_receive_funding(self, mock_symbol_map, mock_request):
        mock_symbol_map.return_value = {
            self.ex_trading_pair: self.trading_pair
        }

        # Test 2: Support trading pair. Payment > Decimal("0")
        self._set_mock_response(mock_request, 200, {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": 0.0001,
                "exec_fee": 0.00000002,
                "exec_timestamp": 1575907200
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        })

        self.connector_task = self.ev_loop.create_task(
            self.connector._fetch_funding_fee(self.trading_pair)
        )
        result = self.ev_loop.run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue("INFO", "Funding payment of 0.0001 received on COINALPHA-HBOT market.")

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source.BybitPerpetualAPIOrderBookDataSource.trading_pair_symbol_map", new_callable=AsyncMock)
    def test_fetch_funding_fee_supported_trading_pair_paid_funding(self, mock_symbol_map, mock_request):
        mock_symbol_map.return_value = {
            self.ex_trading_pair: self.trading_pair
        }

        self._set_mock_response(mock_request, 200, {
            "ret_code": 0,
            "ret_msg": "error",
            "ext_code": "",
            "result": {
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": -0.0001,
                "exec_fee": 0.00000002,
                "exec_timestamp": 1575907200
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        })

        self.connector_task = self.ev_loop.create_task(
            self.connector._fetch_funding_fee(self.trading_pair)
        )
        result = self.ev_loop.run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue(self._is_logged('INFO', "Funding payment of -0.0001 paid on COINALPHA-HBOT market."))
