import asyncio
import json
import unittest
from typing import Any, List, Dict
from unittest.mock import patch, AsyncMock

import pandas as pd

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import BinancePerpetualDerivative
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BinancePerpetualDerivativeUnitTest(unittest.TestCase):
    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    @patch("hummingbot.connector.exchange.binance.binance_time.BinanceTime.start")
    def setUp(self, mocked_binance_time_start) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.api_responses = asyncio.Queue()

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self._finalMessage = 'FinalDummyMessage'

        self.exchange = BinancePerpetualDerivative(
            binance_perpetual_api_key="testAPIKey",
            binance_perpetual_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
        )

        self.mocking_assistant = NetworkMockingAssistant()

    async def _get_next_api_response(self):
        message = await self.api_responses.get()
        self.api_responses.task_done()
        return message

    def _set_mock_response(self, mock_api, status: int, json_data: Any, text_data: str = ""):
        self.api_responses.put_nowait(json_data)
        mock_api.return_value.status = status
        mock_api.return_value.json.side_effect = self._get_next_api_response
        mock_api.return_value.text = AsyncMock(return_value=text_data)

    async def _await_all_api_responses_delivered(self):
        await self.api_responses.join()

    def _get_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = [
            {
                "symbol": self.symbol,
                "positionAmt": "1",
                "entryPrice": "10",
                "markPrice": "11",
                "unRealizedProfit": "1",
                "liquidationPrice": "100",
                "leverage": "1",
                "maxNotionalValue": "9",
                "marginType": "cross",
                "isolatedMargin": "0",
                "isAutoAddMargin": "false",
                "positionSide": "BOTH",
                "notional": "11",
                "isolatedWallet": "0",
                "updateTime": int(self.start_timestamp),
            }
        ]
        return positions

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.recv.side_effect = self._get_next_ws_received_message
        return ws

    async def _get_next_ws_received_message(self):
        message = await self.ws_incoming_messages.get()
        if json.loads(message) == self._finalMessage:
            self.resume_test_event.set()
        return message

    def _get_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            "e": "ACCOUNT_UPDATE",
            "E": 1564745798939,
            "T": 1564745798938,
            "a": {
                "m": "POSITION",
                "B": [
                    {
                        "a": "USDT",
                        "wb": "122624.12345678",
                        "cw": "100.12345678",
                        "bc": "50.12345678"
                    },
                ],
                "P": [
                    {
                        "s": self.symbol,
                        "pa": "1",
                        "ep": "10",
                        "cr": "200",
                        "up": "1",
                        "mt": "cross",
                        "iw": "0.00000000",
                        "ps": "BOTH"
                    },
                ]
            }
        }
        return account_update

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_existing_account_position_detected_on_positions_update(self, req_mock):
        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, positions)

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.trading_pair.replace("-", ""), self.symbol)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_account_position_updated_on_positions_update(self, req_mock):
        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        positions[0]["positionAmt"] = "2"
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_new_account_position_detected_on_positions_update(self, req_mock):
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, [])
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_closed_account_position_removed_on_positions_update(self, req_mock):
        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions[0]["positionAmt"] = "0"
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    @patch("websockets.connect", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_new_account_position_detected_on_stream_event(self, post_mock, ws_connect_mock, req_mock):
        self.mocking_assistant.configure_http_request_mock(post_mock)
        self.mocking_assistant.add_http_response(post_mock, 200, {"listenKey": "someListenKey"})

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        account_update = self._get_account_update_ws_event_single_position_dict()
        self.mocking_assistant.add_websocket_text_message(ws_connect_mock.return_value, json.dumps(account_update))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, positions)

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.3))

        self.assertEqual(len(self.exchange.account_positions), 1)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    @patch("websockets.connect", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_account_position_updated_on_stream_event(self, post_mock, ws_connect_mock, req_mock):
        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.mocking_assistant.configure_http_request_mock(post_mock)
        self.mocking_assistant.add_http_response(post_mock, 200, {"listenKey": "someListenKey"})
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())
        self.ev_loop.run_until_complete(self._await_all_api_responses_delivered())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        account_update = self._get_account_update_ws_event_single_position_dict()
        account_update["a"]["P"][0]["pa"] = 2
        self.mocking_assistant.add_websocket_text_message(ws_connect_mock.return_value, json.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.ev_loop.run_until_complete(asyncio.sleep(0.3))

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    @patch("websockets.connect", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_closed_account_position_removed_on_stream_event(self, post_mock, ws_connect_mock, req_mock):
        positions = self._get_position_risk_api_endpoint_single_position_list()
        self.mocking_assistant.configure_http_request_mock(req_mock)
        self.mocking_assistant.add_http_response(req_mock, 200, positions)
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.ev_loop.run_until_complete(task)

        self.mocking_assistant.configure_http_request_mock(post_mock)
        self.mocking_assistant.add_http_response(post_mock, 200, {"listenKey": "someListenKey"})
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())
        self.ev_loop.run_until_complete(self._await_all_api_responses_delivered())

        self.assertEqual(len(self.exchange.account_positions), 1)

        account_update = self._get_account_update_ws_event_single_position_dict()
        account_update["a"]["P"][0]["pa"] = 0
        self.mocking_assistant.add_websocket_text_message(ws_connect_mock.return_value, json.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.ev_loop.run_until_complete(asyncio.sleep(0.3))

        self.assertEqual(len(self.exchange.account_positions), 0)
