import asyncio
import json
import re
from datetime import datetime, timezone
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.data_feed.candles_feed.evedex_perpetual_candles import EvedexPerpetualCandles, constants as CONSTANTS


class TestEvedexPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "XRP"
        cls.quote_asset = "USDT"
        cls.interval = "15m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = "XRPUSD"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = EvedexPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed._instrument_resolved = True
        self.data_feed._ex_trading_pair = self.ex_trading_pair

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        base_ts = 1710000000
        return [
            [base_ts + 0, "1.0", "1.2", "0.9", "1.1", "10", "100", "0", "0", "0"],
            [base_ts + 900, "1.1", "1.3", "1.0", "1.2", "11", "110", "0", "0", "0"],
            [base_ts + 1800, "1.2", "1.4", "1.1", "1.3", "12", "120", "0", "0", "0"],
            [base_ts + 2700, "1.3", "1.5", "1.2", "1.4", "13", "130", "0", "0", "0"],
            [base_ts + 3600, "1.4", "1.6", "1.3", "1.5", "14", "140", "0", "0", "0"],
        ]

    def get_candles_rest_data_mock(self):
        base_ts = 1710000000
        return [
            [int((base_ts + 0) * 1000), "1.0", "1.1", "1.2", "0.9", "100", "10"],
            [int((base_ts + 900) * 1000), "1.1", "1.2", "1.3", "1.0", "110", "11"],
            [int((base_ts + 1800) * 1000), "1.2", "1.3", "1.4", "1.1", "120", "12"],
            [int((base_ts + 2700) * 1000), "1.3", "1.4", "1.5", "1.2", "130", "13"],
            [int((base_ts + 3600) * 1000), "1.4", "1.5", "1.6", "1.3", "140", "14"],
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "push": {
                "channel": "market-data:last-candlestick-XRPUSD-15m",
                "pub": {"data": [1710004500000, "1.5", "1.6", "1.7", "1.4", "150", "15"], "offset": 1},
            }
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "push": {
                "channel": "market-data:last-candlestick-XRPUSD-15m",
                "pub": {"data": [1710005400000, "1.6", "1.7", "1.8", "1.5", "160", "16"], "offset": 2},
            }
        }

    @staticmethod
    def _success_subscription_mock():
        return {"result": "ok"}

    @aioresponses()
    async def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        resp = await self.data_feed.fetch_candles(start_time=int(self.start_time), end_time=int(self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_klines(self, ws_connect_mock, mock_time: AsyncMock):
        mock_time.return_value = 1710000000
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_klines = self._success_subscription_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_klines),
        )

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.1)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )
        # First message is Centrifugo connect, second is subscribe
        self.assertGreaterEqual(len(sent_messages), 2)
        self.assertIn("connect", sent_messages[0])

        expected_subscribe = self.data_feed.ws_subscription_payload()
        if "id" in expected_subscribe:
            del expected_subscribe["id"]
        if "id" in sent_messages[1]:
            del sent_messages[1]["id"]
        self.assertEqual(expected_subscribe, sent_messages[1])

        self.assertTrue(self.is_logged("INFO", "Subscribed to public klines..."))

    def test_normalize_timestamp_rounds_to_interval(self):
        ts_ms = 1710004500000 + 1234
        normalized = self.data_feed._normalize_timestamp(ts_ms)
        self.assertEqual(1710004500, normalized)

    def test_properties(self):
        self.assertEqual(CONSTANTS.MARKET_DATA_REST_URL, self.data_feed.rest_url)
        self.assertEqual(CONSTANTS.WSS_URL, self.data_feed.wss_url)
        self.assertEqual(
            f"{CONSTANTS.EXCHANGE_REST_URL}{CONSTANTS.HEALTH_CHECK_ENDPOINT}",
            self.data_feed.health_check_url,
        )
        self.assertEqual(CONSTANTS.CANDLES_ENDPOINT, self.data_feed.candles_endpoint)
        self.assertEqual(CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST,
                         self.data_feed.candles_max_result_per_rest_request)
        self.assertEqual(CONSTANTS.RATE_LIMITS, self.data_feed.rate_limits)
        self.assertEqual(CONSTANTS.INTERVALS, self.data_feed.intervals)
        self.assertIn(self.ex_trading_pair, self.data_feed.candles_url)

    async def test_check_network(self):
        rest_assistant = AsyncMock()
        self.data_feed._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        status = await self.data_feed.check_network()

        self.assertEqual(NetworkStatus.CONNECTED, status)
        rest_assistant.execute_request.assert_awaited_once_with(
            url=self.data_feed.health_check_url,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT,
        )

    async def test_initialize_exchange_data_skips_when_resolved(self):
        self.data_feed._instrument_resolved = True
        rest_assistant = AsyncMock()
        self.data_feed._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        await self.data_feed.initialize_exchange_data()

        rest_assistant.execute_request.assert_not_called()

    async def test_initialize_exchange_data_handles_exception(self):
        self.data_feed._instrument_resolved = False
        rest_assistant = AsyncMock()
        rest_assistant.execute_request.side_effect = Exception("boom")
        self.data_feed._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        await self.data_feed.initialize_exchange_data()

        self.assertTrue(self.data_feed._instrument_resolved)
        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Failed to resolve Evedex instrument name from exchange info. Using derived symbol.",
            )
        )

    async def test_initialize_exchange_data_resolves_instrument(self):
        self.data_feed._instrument_resolved = False
        self.data_feed._ex_trading_pair = "OLD"
        rest_assistant = AsyncMock()
        rest_assistant.execute_request.return_value = {
            "list": [
                {
                    "from": {"symbol": self.base_asset},
                    "to": {"symbol": "USD"},
                    "name": "XRPUSD",
                }
            ]
        }
        self.data_feed._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        await self.data_feed.initialize_exchange_data()

        self.assertEqual("XRPUSD", self.data_feed._ex_trading_pair)
        self.assertTrue(self.data_feed._instrument_resolved)

    def test_format_iso_timestamp_handles_seconds_and_ns(self):
        ts_seconds = 1710000000
        expected_seconds = datetime.fromtimestamp(ts_seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.assertEqual(expected_seconds, self.data_feed._format_iso_timestamp(ts_seconds))

        ts_ns = 171000000000000000
        expected_ns = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.assertEqual(expected_ns, self.data_feed._format_iso_timestamp(ts_ns))

    def test_get_rest_candles_params_includes_after_before(self):
        with patch.object(self.data_feed, "_format_iso_timestamp", side_effect=["after", "before"]):
            params = self.data_feed._get_rest_candles_params(start_time=1, end_time=2)
        self.assertEqual(
            {
                "group": CONSTANTS.INTERVALS[self.interval],
                "after": "after",
                "before": "before",
            },
            params,
        )

    def test_parse_rest_candles_variants(self):
        list_row = [1710000000000, "1", "1.1", "1.2", "0.9", "100", "10"]
        dict_row = {
            "timestamp": 1710000900000,
            "open": "1",
            "high": "1.2",
            "low": "0.9",
            "close": "1.1",
            "volume": "5",
            "quoteVolume": "50",
        }
        parsed = self.data_feed._parse_rest_candles({"data": [list_row, dict_row, "bad"]})
        self.assertEqual(2, len(parsed))
        self.assertLess(parsed[0][0], parsed[1][0])

        self.assertEqual([], self.data_feed._parse_rest_candles({"data": "bad"}))
        self.assertEqual([], self.data_feed._parse_rest_candles(None))

    def test_parse_candle_row_variants(self):
        self.assertIsNone(self.data_feed._parse_candle_row([1, 2, 3]))

        row_len_6 = [1710000000000, "1", "1.1", "1.2", "0.9", "10"]
        parsed_len_6 = self.data_feed._parse_candle_row(row_len_6)
        self.assertEqual("10", parsed_len_6[5])
        self.assertEqual(0, parsed_len_6[6])

        row_len_7 = [1710000000000, "1", "1.1", "1.2", "0.9", "100", "10"]
        parsed_len_7 = self.data_feed._parse_candle_row(row_len_7)
        self.assertEqual("10", parsed_len_7[5])
        self.assertEqual("100", parsed_len_7[6])

    def test_parse_candle_dict_variants(self):
        self.assertIsNone(self.data_feed._parse_candle_dict({"open": "1"}))

        full = {
            "timestamp": 1710000000000,
            "open": "1",
            "high": "1.2",
            "low": "0.9",
            "close": "1.1",
            "volume": "5",
            "volumeUsd": "50",
        }
        parsed_full = self.data_feed._parse_candle_dict(full)
        self.assertEqual("50", parsed_full[6])

        short = {
            "t": 1710000000000,
            "o": "1",
            "h": "1.2",
            "l": "0.9",
            "c": "1.1",
            "v": "5",
            "quoteVolume": "60",
        }
        parsed_short = self.data_feed._parse_candle_dict(short)
        self.assertEqual("60", parsed_short[6])

        fallback = {
            "t": 1710000000000,
            "o": "1",
            "h": "1.2",
            "l": "0.9",
            "c": "1.1",
            "v": "5",
            "q": "70",
        }
        parsed_fallback = self.data_feed._parse_candle_dict(fallback)
        self.assertEqual("70", parsed_fallback[6])

    def test_next_message_id_and_subscription_channels(self):
        first = self.data_feed._next_message_id()
        second = self.data_feed._next_message_id()
        self.assertEqual(first + 1, second)

        self.data_feed._ex_trading_pair = "XRP-USD"
        channels = self.data_feed._subscription_channels()
        self.assertIn("market-data:last-candlestick-XRP-USD-15m", channels)
        self.assertIn("market-data:last-candlestick-XRPUSD-15m", channels)
        self.assertEqual(2, len(channels))

    def test_ws_access_token_from_constructor(self):
        self.data_feed._ws_access_token = None
        self.assertIsNone(self.data_feed._ws_access_token)

        tokenized_data_feed = EvedexPerpetualCandles(
            trading_pair=self.trading_pair,
            interval=self.interval,
            ws_access_token="token",
        )
        self.assertEqual("token", tokenized_data_feed._ws_access_token)

    def test_ws_subscription_payload_includes_access_token(self):
        self.data_feed._ws_access_token = "token"
        payload = self.data_feed.ws_subscription_payload()
        self.assertEqual({"accessToken": "token"}, payload["subscribe"]["data"])

    async def test_subscribe_channels_success_sends_requests(self):
        ws = AsyncMock()
        self.data_feed._ws_access_token = "token"
        with patch.object(self.data_feed, "_subscription_channels", return_value=["chan1", "chan2"]):
            await self.data_feed._subscribe_channels(ws)

        self.assertEqual(2, ws.send.await_count)
        first_payload = ws.send.call_args_list[0][0][0].payload
        self.assertEqual("chan1", first_payload["subscribe"]["channel"])
        self.assertEqual({"accessToken": "token"}, first_payload["subscribe"]["data"])
        self.assertTrue(self.is_logged("INFO", "Subscribed to public klines..."))

    async def test_ping_loop_logs_error(self):
        ws = AsyncMock()
        ws.send.side_effect = Exception("boom")
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await self.data_feed._ping_loop(ws)

        self.assertTrue(self.is_logged("DEBUG", "Ping loop error: boom"))

    async def test_connected_websocket_assistant_cancels_ping_and_sends_connect(self):
        pending_event = asyncio.Event()
        pending_task = asyncio.create_task(pending_event.wait())
        self.data_feed._ping_task = pending_task

        ws = AsyncMock()
        self.data_feed._api_factory.get_ws_assistant = AsyncMock(return_value=ws)

        result = await self.data_feed._connected_websocket_assistant()

        self.assertIs(result, ws)
        self.assertIsNone(self.data_feed._ping_task)
        self.assertTrue(pending_task.cancelled())
        ws.connect.assert_awaited_once()
        ws.send.assert_awaited_once()
        connect_payload = ws.send.call_args[0][0].payload
        self.assertIn("connect", connect_payload)
        self.assertIs(self.data_feed._ws_assistant, ws)

    def test_parse_websocket_message_variants(self):
        self.assertIsNone(self.data_feed._parse_websocket_message(None))

        empty = self.data_feed._parse_websocket_message({})
        self.assertIsInstance(empty, WSJSONRequest)
        self.assertEqual({}, empty.payload)

        pong = self.data_feed._parse_websocket_message({"ping": {}})
        self.assertIsInstance(pong, WSJSONRequest)
        self.assertEqual({"pong": {}}, pong.payload)

        self.assertIsNone(self.data_feed._parse_websocket_message({"push": {"pub": {}}}))

        list_payload = {
            "push": {
                "pub": {"data": [1710000000000, "1", "1.1", "1.2", "0.9", "100", "10"]}
            }
        }
        parsed_list = self.data_feed._parse_websocket_message(list_payload)
        self.assertEqual("1", parsed_list["open"])

        nested_list_payload = {"data": {"data": [1710000000000, "1", "1.1", "1.2", "0.9", "100", "10"]}}
        parsed_nested = self.data_feed._parse_websocket_message(nested_list_payload)
        self.assertEqual("1.1", parsed_nested["close"])

        dict_payload = {
            "data": {
                "t": 1710000000000,
                "o": "1",
                "h": "1.2",
                "l": "0.9",
                "c": "1.1",
                "v": "10",
                "q": "100",
            }
        }
        parsed_dict = self.data_feed._parse_websocket_message(dict_payload)
        self.assertEqual("1.1", parsed_dict["close"])

        self.assertIsNone(self.data_feed._parse_websocket_message({"data": "bad"}))

    async def test_on_order_stream_interruption_cancels_ping(self):
        pending_event = asyncio.Event()
        pending_task = asyncio.create_task(pending_event.wait())
        self.data_feed._ping_task = pending_task
        self.data_feed._candles.extend(self._candles_data_mock())

        ws = MagicMock()
        ws.disconnect = AsyncMock()

        await self.data_feed._on_order_stream_interruption(ws)
        await asyncio.sleep(0)

        self.assertIsNone(self.data_feed._ping_task)
        self.assertTrue(pending_task.cancelled())
        ws.disconnect.assert_awaited_once()
        self.assertEqual(0, len(self.data_feed._candles))
