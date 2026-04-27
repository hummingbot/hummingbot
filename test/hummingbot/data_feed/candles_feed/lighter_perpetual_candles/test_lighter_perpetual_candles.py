import asyncio
import json
import re
import time
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase
from unittest.mock import AsyncMock, patch

import numpy as np
from aioresponses import aioresponses

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.lighter_perpetual_candles import LighterPerpetualCandles


class TestLighterPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    # Market ID used throughout tests (normally resolved by initialize_exchange_data via REST)
    MARKET_ID = 200

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"  # Lighter returns trading_pair as-is
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = LighterPerpetualCandles(
            trading_pair=self.trading_pair,
            interval=self.interval,
            max_records=self.max_records,
        )
        # Bypass initialize_exchange_data — set market_id directly
        self.data_feed._market_id = self.MARKET_ID
        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    def tearDown(self) -> None:
        self.data_feed.stop()
        super().tearDown()

    # ── Required data mocks ────────────────────────────────────────────────────

    @staticmethod
    def get_candles_rest_data_mock():
        """REST API response format: {"c": [...candle dicts...]}"""
        return {
            "c": [
                {"t": 1718895600000, "o": "64942.0", "h": "65123.0", "l": "64812.0", "c": "64837.0",
                 "v": "190.58", "V": "12345.0", "i": 100},
                {"t": 1718899200000, "o": "64837.0", "h": "64964.0", "l": "64564.0", "c": "64898.0",
                 "v": "271.68", "V": "17654.0", "i": 200},
                {"t": 1718902800000, "o": "64900.0", "h": "65034.0", "l": "64714.0", "c": "64997.0",
                 "v": "104.80", "V": "6810.0", "i": 150},
                {"t": 1718906400000, "o": "64999.0", "h": "65244.0", "l": "64981.0", "c": "65157.0",
                 "v": "158.51", "V": "10310.0", "i": 175},
                {"t": 1718910000000, "o": "65153.0", "h": "65153.0", "l": "64882.0", "c": "65095.0",
                 "v": "209.75", "V": "13650.0", "i": 190},
            ]
        }

    def get_fetch_candles_data_mock(self):
        """Expected output from _parse_rest_candles: rows of [ts, o, h, l, c, v, V, i, 0, 0]"""
        return [
            [1718895600.0, 64942.0, 65123.0, 64812.0, 64837.0, 190.58, 12345.0, 100.0, 0.0, 0.0],
            [1718899200.0, 64837.0, 64964.0, 64564.0, 64898.0, 271.68, 17654.0, 200.0, 0.0, 0.0],
            [1718902800.0, 64900.0, 65034.0, 64714.0, 64997.0, 104.80, 6810.0, 150.0, 0.0, 0.0],
            [1718906400.0, 64999.0, 65244.0, 64981.0, 65157.0, 158.51, 10310.0, 175.0, 0.0, 0.0],
            [1718910000.0, 65153.0, 65153.0, 64882.0, 65095.0, 209.75, 13650.0, 190.0, 0.0, 0.0],
        ]

    def get_candles_ws_data_mock_1(self):
        """Lighter WS trade event — triggers REST fetch for latest candle."""
        return {
            "channel": f"trade:{self.MARKET_ID}",
            "data": {"price": "65162.0", "size": "0.1", "created_at": 1718914860},
        }

    def get_candles_ws_data_mock_2(self):
        """Second trade event with a later timestamp → new candle bucket."""
        return {
            "channel": f"trade:{self.MARKET_ID}",
            "data": {"price": "65200.0", "size": "0.2", "created_at": 1718918460},
        }

    @staticmethod
    def _success_subscription_mock():
        """Server-sent subscription confirmation (channel uses '/' — won't match trade filter)."""
        return {"type": "subscribed", "channel": "trade/200"}

    # ── Test overrides ─────────────────────────────────────────────────────────

    @aioresponses()
    async def test_fetch_candles(self, mock_api):
        """GET-based fetch: mock with mock_api.get and verify parsed shape."""
        regex_url = re.compile(
            f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(url=regex_url, body=json.dumps(self.get_candles_rest_data_mock()))

        resp = await self.data_feed.fetch_candles(
            start_time=int(self.start_time),
            end_time=int(self.end_time),
        )

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles", new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_klines(
            self, ws_connect_mock, mock_time, fetch_candles_mock):
        """Verify subscription payload is sent; mock fetch_candles to avoid real network seed call."""
        mock_time.return_value = time.time()
        fetch_candles_mock.return_value = np.array([])  # seed returns empty, no network needed
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self._success_subscription_mock()))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.1)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent))
        expected = self.data_feed.ws_subscription_payload()
        self.assertEqual(expected, sent[0])
        self.assertTrue(self.is_logged("INFO", "Subscribed to public klines..."))

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles",
           new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_empty_candle(
            self, ws_connect_mock, fetch_candles_mock, fill_historical_candles_mock):
        """
        When a trade event arrives and the candle deque is empty, the REST-fetched
        candle is appended and fill_historical_candles is triggered.
        """
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        candle = np.array([[1718914860.0, 65162.0, 65200.0, 65100.0, 65162.0, 0.1, 0.0, 1.0, 0.0, 0.0]])
        # First call = seed (empty); second call = trade-event REST fetch
        fetch_candles_mock.side_effect = [np.array([]), candle]

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.3)

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)
        fill_historical_candles_mock.assert_called_once()

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles",
           new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_duplicated_candle_not_included(
            self, ws_connect_mock, fetch_candles_mock, fill_historical_candles_mock):
        """Two identical trade events must not insert duplicate candles."""
        fill_historical_candles_mock.return_value = None
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        candle = np.array([[1718914860.0, 65162.0, 65200.0, 65100.0, 65162.0, 0.1, 0.0, 1.0, 0.0, 0.0]])
        # seed empty; both trade events return the same candle
        fetch_candles_mock.side_effect = [np.array([]), candle, candle]

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            ws_connect_mock.return_value, timeout=2)
        await asyncio.sleep(0.3)

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles",
           new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_with_two_valid_messages(
            self, ws_connect_mock, fetch_candles_mock, _):
        """Two trade events at different timestamps each produce a new candle row."""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        candle1 = np.array([[1718914860.0, 65162.0, 65200.0, 65100.0, 65162.0, 0.1, 0.0, 1.0, 0.0, 0.0]])
        candle2 = np.array([[1718918460.0, 65200.0, 65250.0, 65100.0, 65200.0, 0.2, 0.0, 2.0, 0.0, 0.0]])
        fetch_candles_mock.side_effect = [np.array([]), candle1, candle2]

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_2()))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.3)

        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    # ── Unit tests for Lighter-specific logic ──────────────────────────────────

    def test_name_property(self):
        """name should be lighter_perpetual_{trading_pair}."""
        self.assertEqual(self.data_feed.name, f"lighter_perpetual_{self.trading_pair}")

    def test_ws_subscription_payload(self):
        """Subscription uses 'trade/{market_id}' with a slash."""
        payload = self.data_feed.ws_subscription_payload()
        self.assertEqual(payload["type"], "subscribe")
        self.assertEqual(payload["channel"], f"trade/{self.MARKET_ID}")

    def test_parse_rest_candles_field_mapping(self):
        """Verify every REST JSON field maps to the correct column position."""
        data = {
            "c": [
                {"t": 1718895600000, "o": "100.0", "h": "110.0", "l": "90.0", "c": "105.0",
                 "v": "50.0", "V": "5000.0", "i": 42},
            ]
        }
        result = self.data_feed._parse_rest_candles(data)
        self.assertEqual(len(result), 1)
        row = result[0]
        # Columns: timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, tbv, tbqv
        self.assertEqual(row[0], 1718895600.0)  # t (ms) / 1000 → timestamp in seconds
        self.assertEqual(row[1], 100.0)          # o → open
        self.assertEqual(row[2], 110.0)          # h → high
        self.assertEqual(row[3], 90.0)           # l → low
        self.assertEqual(row[4], 105.0)          # c → close
        self.assertEqual(row[5], 50.0)           # v → volume
        self.assertEqual(row[6], 5000.0)         # V → quote_asset_volume
        self.assertEqual(row[7], 42.0)           # i → n_trades
        self.assertEqual(row[8], 0.0)            # taker_buy_base_volume (always 0)
        self.assertEqual(row[9], 0.0)            # taker_buy_quote_volume (always 0)

    def test_parse_rest_candles_end_time_filter(self):
        """Rows whose timestamp exceeds end_time are excluded."""
        data = {
            "c": [
                {"t": 1718895600000, "o": "100.0", "h": "110.0", "l": "90.0", "c": "105.0",
                 "v": "50.0", "V": "5000.0", "i": 1},
                {"t": 1718899200000, "o": "105.0", "h": "115.0", "l": "95.0", "c": "110.0",
                 "v": "60.0", "V": "6000.0", "i": 2},  # ts (in s after /1000) > end_time → excluded
            ]
        }
        result = self.data_feed._parse_rest_candles(data, end_time=1718897000)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 1718895600.0)

    def test_parse_rest_candles_empty_response(self):
        """Empty 'c' list returns empty list without errors."""
        self.assertEqual(self.data_feed._parse_rest_candles({"c": []}), [])
        self.assertEqual(self.data_feed._parse_rest_candles({}), [])

    def test_get_rest_candles_params(self):
        """REST params include market_id, resolution, timestamps, and count_back."""
        start_ts = 1718895600
        end_ts = 1718910000
        params = self.data_feed._get_rest_candles_params(
            start_time=start_ts, end_time=end_ts, limit=100)
        self.assertEqual(params["market_id"], self.MARKET_ID)
        self.assertEqual(params["start_timestamp"], start_ts)
        self.assertEqual(params["end_timestamp"], end_ts)
        self.assertEqual(params["count_back"], 100)
        self.assertEqual(params["set_timestamp_to_end"], "true")
        self.assertIn("resolution", params)

    async def test_initialize_exchange_data_resolves_perp_market_id(self):
        """initialize_exchange_data picks the perp market using just base symbol (not base/quote)."""
        order_books_response = {
            "order_books": [
                {"market_type": "spot", "symbol": "BTC/USDC", "market_id": 999},
                {"market_type": "perp", "symbol": "ETH", "market_id": 50},
                {"market_type": "perp", "symbol": "BTC", "market_id": self.MARKET_ID},
            ]
        }
        with patch.object(self.data_feed._api_factory, "get_rest_assistant") as mock_get:
            mock_rest = AsyncMock()
            mock_get.return_value = mock_rest
            mock_rest.execute_request.return_value = order_books_response
            self.data_feed._market_id = None
            await self.data_feed.initialize_exchange_data()
        self.assertEqual(self.data_feed._market_id, self.MARKET_ID)

    async def test_initialize_exchange_data_ignores_spot_markets(self):
        """A spot market with matching symbol must not be selected for a perp feed."""
        order_books_response = {
            "order_books": [
                {"market_type": "spot", "symbol": "BTC", "market_id": 999},
            ]
        }
        with patch.object(self.data_feed._api_factory, "get_rest_assistant") as mock_get:
            mock_rest = AsyncMock()
            mock_get.return_value = mock_rest
            mock_rest.execute_request.return_value = order_books_response
            self.data_feed._market_id = None
            with self.assertRaises(ValueError):
                await self.data_feed.initialize_exchange_data()

    async def test_initialize_exchange_data_raises_when_market_not_found(self):
        """ValueError is raised when no perp market matches the base symbol."""
        order_books_response = {
            "order_books": [
                {"market_type": "perp", "symbol": "ETH", "market_id": 50},
            ]
        }
        with patch.object(self.data_feed._api_factory, "get_rest_assistant") as mock_get:
            mock_rest = AsyncMock()
            mock_get.return_value = mock_rest
            mock_rest.execute_request.return_value = order_books_response
            self.data_feed._market_id = None
            with self.assertRaises(ValueError) as ctx:
                await self.data_feed.initialize_exchange_data()
        self.assertIn("BTC", str(ctx.exception))

    async def test_check_network_returns_connected(self):
        """check_network() returns CONNECTED when the health-check endpoint responds."""
        with patch.object(self.data_feed._api_factory, "get_rest_assistant") as mock_get:
            mock_rest = AsyncMock()
            mock_get.return_value = mock_rest
            mock_rest.execute_request.return_value = {"order_books": []}
            result = await self.data_feed.check_network()
        self.assertEqual(result, NetworkStatus.CONNECTED)

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles",
           new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_seed_populates_deque_on_ws_connect(
            self, ws_connect_mock, fetch_candles_mock, fill_historical_candles_mock):
        """When the seed REST call returns candles, they are immediately loaded into the deque."""
        fill_historical_candles_mock.return_value = None
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        seed_candles = np.array([
            [1718895600.0, 64942.0, 65123.0, 64812.0, 64837.0, 190.58, 12345.0, 100.0, 0.0, 0.0],
            [1718899200.0, 64837.0, 64964.0, 64564.0, 64898.0, 271.68, 17654.0, 200.0, 0.0, 0.0],
        ])
        fetch_candles_mock.return_value = seed_candles

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
        await asyncio.sleep(0.3)

        self.assertEqual(len(self.data_feed._candles), 2)
        self.assertTrue(self.data_feed._ws_candle_available.is_set())
        self.listening_task.cancel()

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles",
           new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_same_timestamp_trade_event_replaces_last_candle(
            self, ws_connect_mock, fetch_candles_mock, fill_historical_candles_mock):
        """A trade event at the same timestamp as the current open candle updates it in-place."""
        fill_historical_candles_mock.return_value = None
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ts = 1718914800.0
        original = np.array([ts, 65162.0, 65200.0, 65100.0, 65162.0, 0.1, 0.0, 1.0, 0.0, 0.0])
        self.data_feed._candles.append(original)
        self.data_feed._ws_candle_available.set()

        # Same ts but updated high and close — should replace, not append
        updated = np.array([[ts, 65162.0, 65300.0, 65100.0, 65250.0, 0.3, 0.0, 2.0, 0.0, 0.0]])
        fetch_candles_mock.side_effect = [np.array([]), updated]

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.3)

        self.assertEqual(len(self.data_feed._candles), 1)     # not appended
        self.assertEqual(self.data_feed._candles[-1][2], 65300.0)  # high updated
        self.assertEqual(self.data_feed._candles[-1][4], 65250.0)  # close updated

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_wrong_channel_message_is_ignored(self, ws_connect_mock, fetch_candles_mock):
        """Trade events for a different market_id channel must not trigger a REST fetch."""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        fetch_candles_mock.return_value = np.array([])  # seed returns empty

        wrong_channel_msg = {
            "channel": "trade:999",  # different market
            "data": {"price": "1000.0", "size": "0.1", "created_at": 1718914860},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(wrong_channel_msg))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.3)

        self.assertEqual(len(self.data_feed._candles), 0)
        self.assertEqual(fetch_candles_mock.call_count, 1)

    def test_get_exchange_trading_pair_returns_pair_unchanged(self):
        """For Lighter, the exchange symbol is identical to the internal trading pair."""
        self.assertEqual(
            self.data_feed.get_exchange_trading_pair("ETH-USDC"), "ETH-USDC")
        self.assertEqual(
            self.data_feed.get_exchange_trading_pair("BTC-USDC"), "BTC-USDC")

    # ------------------------------------------------------------------ #
    # Additional branch coverage for missing CI lines                     #
    # ------------------------------------------------------------------ #

    def test_rest_url_property(self):
        """rest_url must return the REST_URL constant (covers line 73)."""
        from hummingbot.data_feed.candles_feed.lighter_perpetual_candles.lighter_perpetual_candles import REST_URL
        self.assertEqual(REST_URL, self.data_feed.rest_url)

    def test_parse_websocket_message_returns_none(self):
        """_parse_websocket_message always returns None (covers line 177)."""
        self.assertIsNone(self.data_feed._parse_websocket_message({}))
        self.assertIsNone(self.data_feed._parse_websocket_message({"channel": "trade:200", "data": {}}))

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles", new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_handles_connection_error(
            self, ws_connect_mock, mock_time, fetch_candles_mock):
        """ConnectionError during WS session must be caught and logged (covers lines 194, 208)."""
        mock_time.return_value = time.time()
        fetch_candles_mock.return_value = np.array([])

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("test connection error")
            return self.mocking_assistant.create_websocket_mock()

        ws_connect_mock.side_effect = side_effect

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
        await asyncio.sleep(0.3)
        self.listening_task.cancel()
        try:
            await self.listening_task
        except asyncio.CancelledError:
            pass

        self.assertTrue(self.is_logged("WARNING", "The websocket connection was closed (test connection error)"))

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fetch_candles", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_ignores_non_dict_data(
            self, ws_connect_mock, fetch_candles_mock):
        """Non-dict WS messages must be silently skipped (covers line 220)."""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        fetch_candles_mock.return_value = np.array([])

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message="not-a-dict-message",
            message_type="text",
        )

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        await asyncio.sleep(0.2)

        self.assertEqual(len(self.data_feed._candles), 0)
