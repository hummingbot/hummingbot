import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.data_feed.candles_feed.bing_x_spot_candles import BingXSpotCandles


class TestBingXSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        # BingX spot uses the dashed BASE-QUOTE notation natively on both REST and WS.
        cls.ex_trading_pair = cls.trading_pair
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = BingXSpotCandles(trading_pair=self.trading_pair,
                                          interval=self.interval,
                                          max_records=self.max_records)
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.resume_test_event = asyncio.Event()

    @staticmethod
    def get_candles_rest_data_mock():
        # Live payload shape: rows are [openTimeMs, open, high, low, close, volume,
        # closeTimeMs, quoteVolume] and arrive newest-first.
        return {"code": 0, "timestamp": 1718744400000, "data": [
            [1718733600000, "3", "4", "2", "3.5", "30", 1718737199999, "105"],
            [1718730000000, "2", "3", "1", "2.5", "20", 1718733599999, "50"],
            [1718726400000, "1", "2", "0.5", "2", "10", 1718729999999, "20"],
            [1718722800000, "0.5", "1", "0.5", "1", "5", 1718726399999, "5"],
        ]}

    @staticmethod
    def get_fetch_candles_data_mock():
        return [
            [1718722800.0, "0.5", "1", "0.5", "1", "5", "5", 0.0, 0.0, 0.0],
            [1718726400.0, "1", "2", "0.5", "2", "10", "20", 0.0, 0.0, 0.0],
            [1718730000.0, "2", "3", "1", "2.5", "20", "50", 0.0, 0.0, 0.0],
            [1718733600.0, "3", "4", "2", "3.5", "30", "105", 0.0, 0.0, 0.0],
        ]

    @staticmethod
    def get_candles_ws_data_mock_1():
        # Live push shape: the candle is wrapped under data["K"] with data["e"] == "kline".
        return {"code": 0, "dataType": "BTC-USDT@kline_60min", "success": True, "data": {
            "e": "kline", "E": 1718730001000, "s": "BTC-USDT",
            "K": {"t": 1718730000000, "T": 1718733599999, "s": "BTC-USDT", "i": "60min",
                  "o": "2", "c": "2.5", "h": "3", "l": "1", "v": "20", "n": 7, "q": "50"}}}

    @staticmethod
    def get_candles_ws_data_mock_2():
        return {"code": 0, "dataType": "BTC-USDT@kline_60min", "success": True, "data": {
            "e": "kline", "E": 1718733601000, "s": "BTC-USDT",
            "K": {"t": 1718733600000, "T": 1718737199999, "s": "BTC-USDT", "i": "60min",
                  "o": "3", "c": "3.5", "h": "4", "l": "2", "v": "30", "n": 8, "q": "105"}}}

    @staticmethod
    def _success_subscription_mock():
        return {"code": 0, "msg": "SUCCESS"}

    def test_rest_params_use_dashed_symbol_hb_interval_and_milliseconds(self):
        params = self.data_feed._get_rest_candles_params(start_time=1718730000, end_time=1718733600)
        self.assertEqual(params, {
            "symbol": "BTC-USDT", "interval": "1h",
            "startTime": 1718730000000, "endTime": 1718733600000,
            "limit": self.data_feed.candles_max_result_per_rest_request,
        })

    def test_parse_rest_reverses_newest_first_rows_into_ascending_rows(self):
        parsed = self.data_feed._parse_rest_candles(self.get_candles_rest_data_mock())
        self.assertEqual(parsed, self.get_fetch_candles_data_mock())

    def test_ws_subscription_uses_bingx_data_type_vocabulary(self):
        payload = self.data_feed.ws_subscription_payload()
        self.assertEqual(payload["reqType"], "sub")
        self.assertEqual(payload["dataType"], "BTC-USDT@kline_60min")
        self.assertIn("id", payload)

    def test_ws_parser_maps_bingx_candle_fields(self):
        parsed = self.data_feed._parse_websocket_message(self.get_candles_ws_data_mock_1())
        self.assertEqual(parsed, {
            "timestamp": 1718730000, "open": "2", "high": "3", "low": "1", "close": "2.5",
            "volume": "20", "quote_asset_volume": "50", "n_trades": 7,
            "taker_buy_base_volume": 0.0, "taker_buy_quote_volume": 0.0,
        })

    def test_ws_parser_ignores_subscription_acks_and_text_frames(self):
        self.assertIsNone(self.data_feed._parse_websocket_message(self._success_subscription_mock()))
        self.assertIsNone(self.data_feed._parse_websocket_message("Ping"))
        self.assertIsNone(self.data_feed._parse_websocket_message(None))

    def test_ws_parser_decompresses_gzip_frames(self):
        import gzip
        import json
        frame = gzip.compress(json.dumps(self.get_candles_ws_data_mock_1()).encode())
        parsed = self.data_feed._parse_websocket_message(frame)
        self.assertEqual(parsed["timestamp"], 1718730000)
