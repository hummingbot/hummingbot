import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.data_feed.candles_feed.kucoin_spot_candles import KucoinSpotCandles


class TestKucoinSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = KucoinSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [
            [1672981200, '16823.24000000', '16792.12000000', '16810.18000000', '16823.63000000', '6230.44034000', 1672984799999, 0.0, 0.0, 0.0],
            [1672984800, '16809.74000000', '16779.96000000', '16786.86000000', '16816.45000000', '6529.22759000', 1672988399999, 0.0, 0.0, 0.0],
            [1672988400, '16786.60000000', '16780.15000000', '16794.06000000', '16802.87000000', '5763.44917000', 1672991999999, 0.0, 0.0, 0.0],
            [1672992000, '16794.33000000', '16791.47000000', '16802.11000000', '16812.22000000', '5475.13940000', 1672995599999, 0.0, 0.0, 0.0],
        ]

    def get_candles_rest_data_mock(self):
        data = [
            [
                1672981200,
                "16823.24000000",
                "16823.63000000",
                "16792.12000000",
                "16810.18000000",
                "6230.44034000",
                1672984799999,
            ],
            [
                1672984800,
                "16809.74000000",
                "16816.45000000",
                "16779.96000000",
                "16786.86000000",
                "6529.22759000",
                1672988399999,
            ],
            [
                1672988400,
                "16786.60000000",
                "16802.87000000",
                "16780.15000000",
                "16794.06000000",
                "5763.44917000",
                1672991999999,
            ],
            [
                1672992000,
                "16794.33000000",
                "16812.22000000",
                "16791.47000000",
                "16802.11000000",
                "5475.13940000",
                1672995599999,
            ],
        ]
        return {"data": data}

    def get_candles_ws_data_mock_1(self):
        data = {
            "type": "message",
            "topic": "/market/candles:BTC-USDT_1hour",
            "subject": "trade.candles.update",
            "data": {
                "symbol": "BTC-USDT",  # symbol
                "candles": [
                    "1589968800",  # Start time of the candle cycle
                    "9786.9",  # open price
                    "9740.8",  # close price
                    "9806.1",  # high price
                    "9732",  # low price
                    "27.45649579",  # Transaction volume
                    "268280.09830877"  # Transaction amount
                ],
                "time": 1589970010253893337  # now（us）
            }
        }
        return data

    def get_candles_ws_data_mock_2(self):
        data = {
            "type": "message",
            "topic": "/market/candles:BTC-USDT_1hour",
            "subject": "trade.candles.update",
            "data": {
                "symbol": "BTC-USDT",  # symbol
                "candles": [
                    "1589972400",  # Start time of the candle cycle
                    "9786.9",  # open price
                    "9740.8",  # close price
                    "9806.1",  # high price
                    "9732",  # low price
                    "27.45649579",  # Transaction volume
                    "268280.09830877"  # Transaction amount
                ],
                "time": 1589970010253893337  # now（us）
            }
        }
        return data

    @staticmethod
    def _success_subscription_mock():
        return {'id': str(get_tracking_nonce()),
                'privateChannel': False,
                'response': False,
                'topic': '/market/candles:BTC-USDT_1hour',
                'type': 'subscribe'}
