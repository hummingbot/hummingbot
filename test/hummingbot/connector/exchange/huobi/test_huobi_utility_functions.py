import unittest

from hummingbot.connector.exchange.huobi import (
    huobi_constants as CONSTANTS,
    huobi_utils as func_utils,
    huobi_web_utils as web_utils,
)


class HuobiUtilsTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = CONSTANTS.SERVER_TIME_URL
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_private_rest_url(self):
        path_url = CONSTANTS.SERVER_TIME_URL
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url))

    def test_is_exchange_information_valid(self):
        invalid_info = {
            "status": "ok",
            "data": [
                {
                    "symbol": "btc3lusdt",
                    "state": "offline",
                    "bc": "btc3l",
                    "qc": "usdt",
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "minoa": 0.01,
                    "maxoa": 199.0515,
                    "minov": 5,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities"
                }
            ],
            "ts": "1641880897191",
            "full": 1
        }

        self.assertFalse(func_utils.is_exchange_information_valid(invalid_info["data"][0]))

        valid_info = {
            "status": "ok",
            "data": [
                {
                    "symbol": "btc3lusdt",
                    "state": "online",
                    "bc": "btc3l",
                    "qc": "usdt",
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "minoa": 0.01,
                    "maxoa": 199.0515,
                    "minov": 5,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities"
                }
            ],
            "ts": "1641880897191",
            "full": 1
        }
        self.assertTrue(func_utils.is_exchange_information_valid(valid_info["data"][0]))
