import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.bitget_spot_candles import BitgetSpotCandles


class TestBitgetSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = "USDT"
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = BitgetSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()

    @staticmethod
    def get_candles_rest_data_mock():
        """
        Returns a mock response from the exchange REST API endpoint. At least it must contain four candles.
        """
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695800278693,
            "data": [
                [
                    "1758798420000",
                    "111694.49",
                    "111694.49",
                    "111588.85",
                    "111599.04",
                    "3.16054396428",
                    "352892.715820802517",
                    "352892.715820802517"
                ],
                [
                    "1758798480000",
                    "111599.04",
                    "111608.15",
                    "111595.02",
                    "111595.03",
                    "4.59290268736",
                    "512570.995025016836",
                    "512570.995025016836"
                ],
                [
                    "1758798540000",
                    "111595.03",
                    "111595.04",
                    "111521.01",
                    "111529.52",
                    "14.06507470738",
                    "1568969.70849836405",
                    "1568969.70849836405"
                ],
                [
                    "1758798600000",
                    "111529.52",
                    "111569.85",
                    "111529.52",
                    "111548.38",
                    "6.67627652466",
                    "744806.49272433786",
                    "744806.49272433786"
                ]
            ]
        }

    def get_fetch_candles_data_mock(self):
        return [
            [
                1758798420, "111694.49", "111694.49", "111588.85", "111599.04",
                "3.16054396428", "352892.715820802517", 0., 0., 0.
            ],
            [
                1758798480, "111599.04", "111608.15", "111595.02", "111595.03",
                "4.59290268736", "512570.995025016836", 0., 0., 0.
            ],
            [
                1758798540, "111595.03", "111595.04", "111521.01", "111529.52",
                "14.06507470738", "1568969.70849836405", 0., 0., 0.
            ],
            [
                1758798600, "111529.52", "111569.85", "111529.52", "111548.38",
                "6.67627652466", "744806.49272433786", 0., 0., 0.
            ]
        ]

    @staticmethod
    def get_candles_ws_data_mock_1():
        return {
            "action": "update",
            "arg": {
                "instType": "SPOT",
                "channel": "candle1m",
                "instId": "ETHUSDT"
            },
            "data": [
                [
                    "1758798540000",
                    "111595.03",
                    "111595.04",
                    "111521.01",
                    "111529.52",
                    "14.06507470738",
                    "1568969.70849836405",
                    "1568969.70849836405"
                ]
            ],
            "ts": 1695702747821
        }

    @staticmethod
    def get_candles_ws_data_mock_2():
        return {
            "action": "update",
            "arg": {
                "instType": "SPOT",
                "channel": "candle1m",
                "instId": "ETHUSDT"
            },
            "data": [
                [
                    "1758798600000",
                    "111529.52",
                    "111569.85",
                    "111529.52",
                    "111548.38",
                    "6.67627652466",
                    "744806.49272433786",
                    "744806.49272433786"
                ]
            ],
            "ts": 1695702747821
        }

    @staticmethod
    def _success_subscription_mock():
        return {
            "event": "subscribe",
            "arg": {
                "instType": "SPOT",
                "channel": "candle1m",
                "instId": "ETHUSDT"
            }
        }
