import unittest
from datetime import datetime, timezone
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.data_feed.candles_feed.rubin_perpetual_candles import (
    RubinPerpetualCandles,
    RubinPerpetualTestnetCandles,
    constants as CONSTANTS,
)

# Ascending, 60s apart (matches the "1m" interval) so the equidistance checks pass.
_TS = [1718895660, 1718895720, 1718895780, 1718895840, 1718895900]
_PX = [3087.0, 3089.0, 3088.0, 3090.0, 3091.0]


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _candle(ts: int, px: float) -> dict:
    return {
        "startedAt": _iso(ts),
        "open": str(px), "high": str(px), "low": str(px), "close": str(px),
        "baseTokenVolume": "1", "usdVolume": "10", "trades": 5,
    }


class TestRubinPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.trading_pair  # Rubin tickers already use the Hummingbot format
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        # The base class defaults end_time to 10e17, which overflows datetime.fromtimestamp
        # when the feed converts it to an ISO string; use realistic epoch seconds instead.
        self.start_time = _TS[0]
        self.end_time = _TS[-1] + 60
        self.data_feed = RubinPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    def get_fetch_candles_data_mock(self):
        # Parsed rows (ascending), 10 columns, matching _candle() above.
        return [[float(ts), px, px, px, px, 1.0, 10.0, 5.0, 0.0, 0.0] for ts, px in zip(_TS, _PX)]

    @staticmethod
    def get_candles_rest_data_mock():
        # The indexer returns candles newest-first; the feed sorts them ascending.
        return {"candles": [_candle(ts, px) for ts, px in zip(reversed(_TS), reversed(_PX))]}

    @staticmethod
    def get_candles_ws_data_mock_1():
        return {"type": "channel_data", "channel": CONSTANTS.WS_CHANNEL, "contents": _candle(_TS[0], _PX[0])}

    @staticmethod
    def get_candles_ws_data_mock_2():
        return {"type": "channel_data", "channel": CONSTANTS.WS_CHANNEL, "contents": _candle(_TS[1], _PX[1])}

    @staticmethod
    def _success_subscription_mock():
        return {"type": "subscribed", "channel": CONSTANTS.WS_CHANNEL, "id": "BTC-USD/1MIN", "contents": {}}


class RubinPerpetualCandlesDomainTests(unittest.TestCase):
    def test_mainnet_endpoints(self):
        feed = RubinPerpetualCandles(trading_pair="BTC-USD", interval="1m")
        self.assertEqual(feed.rest_url, "https://indexer.mainnet.rubin.trade")
        self.assertEqual(feed.wss_url, "wss://indexer.mainnet.rubin.trade/v4/ws")
        self.assertTrue(feed.candles_url.endswith("/v4/candles/perpetualMarkets/BTC-USD"))

    def test_testnet_endpoints(self):
        feed = RubinPerpetualTestnetCandles(trading_pair="BTC-USD", interval="1m")
        self.assertEqual(feed._domain, "rubin_perpetual_testnet")
        self.assertEqual(feed.rest_url, "https://indexer.testnet.rubin.trade")
        self.assertEqual(feed.wss_url, "wss://indexer.testnet.rubin.trade/v4/ws")

    def test_ws_subscription_payload(self):
        feed = RubinPerpetualCandles(trading_pair="BTC-USD", interval="1m")
        payload = feed.ws_subscription_payload()
        self.assertEqual(payload["type"], "subscribe")
        self.assertEqual(payload["channel"], CONSTANTS.WS_CHANNEL)
        self.assertEqual(payload["id"], "BTC-USD/1MIN")
