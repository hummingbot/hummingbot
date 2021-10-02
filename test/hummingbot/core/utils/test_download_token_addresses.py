import asyncio
import json
import re
import unittest
from typing import Dict, Awaitable
from unittest.mock import patch, MagicMock

from aioresponses import aioresponses

from hummingbot.core.utils.download_token_addresses import (
    DOLOMITE_ENDPOINT,
    download_dolomite_token_addresses,
    RADAR_RELAY_ENDPOINT,
    download_radar_relay_token_addresses,
    BAMBOO_RELAY_ENDPOINT,
    download_bamboo_relay_token_addresses,
    download_erc20_token_addresses,
)


class DownloadTokenAddressesTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(
            asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_dolomite_tokens_mock(
        first_ticker: str, first_identifier: str, second_ticker: str,
        second_identifier: str
    ) -> Dict:
        tokens = {
            "global_objects": {},
            "data": [
                {
                    "dolomite_token_id": 1934,
                    "token_type": "ERC20",
                    "version_number": 1,
                    "identifier": first_identifier,
                    "ticker": first_ticker,
                    "name": {
                        "singular": "Bitcoin",
                        "plural": "Bitcoins"
                    },
                    "display_precision": 8,
                    "precision": 18,
                    "thumbnail_url": "string",
                    "image_url": "string",
                    "date_added": "string (date-time)"
                },
                {
                    "dolomite_token_id": 1935,
                    "token_type": "ERC20",
                    "version_number": 1,
                    "identifier": second_identifier,
                    "ticker": second_ticker,
                    "name": {
                        "singular": "Bitcoin",
                        "plural": "Bitcoins"
                    },
                    "display_precision": 8,
                    "precision": 18,
                    "thumbnail_url": "string",
                    "image_url": "string",
                    "date_added": "string (date-time)"
                }
            ],
            "paging_metadata": None,
            "cursor": None,
            "error": None
        }
        return tokens

    @aioresponses()
    def test_download_dolomite_token_addresses(self, mocked_api):
        url = DOLOMITE_ENDPOINT
        lrc_identifier = "0x0000000000000000000000000000000000000000"
        btc_identifier = "0x0000000000000000000000000000000000000001"
        resp = self.get_dolomite_tokens_mock(
            first_ticker="LRC",
            first_identifier=lrc_identifier,
            second_ticker="BTC",
            second_identifier=btc_identifier,
        )
        mocked_api.get(url, body=json.dumps(resp))
        token_dict = {}

        self.async_run_with_timeout(
            download_dolomite_token_addresses(token_dict))

        self.assertIn("LRC", token_dict)
        self.assertIn("BTC", token_dict)
        self.assertEqual(token_dict["LRC"], lrc_identifier)
        self.assertEqual(token_dict["BTC"], btc_identifier)

    @aioresponses()
    def test_download_dolomite_token_addresses_replaces_lrc_only(self, mocked_api):
        url = DOLOMITE_ENDPOINT
        lrc_identifier = "0x0000000000000000000000000000000000000000"
        btc_identifier = "0x0000000000000000000000000000000000000001"
        resp = self.get_dolomite_tokens_mock(
            first_ticker="LRC",
            first_identifier=lrc_identifier,
            second_ticker="BTC",
            second_identifier=btc_identifier,
        )
        mocked_api.get(url, body=json.dumps(resp))
        another_btc_identifier = "anotherIdentifier"
        token_dict = {"LRC": "someIdentifier", "BTC": another_btc_identifier}

        self.async_run_with_timeout(
            download_dolomite_token_addresses(token_dict))

        self.assertIn("LRC", token_dict)
        self.assertIn("BTC", token_dict)
        self.assertEqual(token_dict["LRC"], lrc_identifier)
        self.assertEqual(token_dict["BTC"], another_btc_identifier)

    @patch("logging.Logger.error")
    @aioresponses()
    def test_download_dolomite_token_addresses_logs_errors(
        self, error_mock: MagicMock, mocked_api
    ):
        url = DOLOMITE_ENDPOINT
        resp = {}
        mocked_api.get(url, body=json.dumps(resp))
        token_dict = {}

        self.async_run_with_timeout(
            download_dolomite_token_addresses(token_dict))

        error_mock.assert_called()

    @aioresponses()
    def test_download_radar_relay_token_addresses(self, mocked_api):
        url = RADAR_RELAY_ENDPOINT
        regex_url = re.compile(f"^{url}")
        btc_address = "0x0000000000000000000000000000000000000000"
        usdt_address = "0x0000000000000000000000000000000000000001"
        resp = [
            {
                "id": "BTC-USDT",
                "baseTokenAddress": btc_address,
                "quoteTokenAddress": usdt_address,
            }
        ]
        mocked_api.get(regex_url, body=json.dumps(resp))
        mocked_api.get(regex_url, body=json.dumps([]))  # to break the loop
        token_dict = {}

        self.async_run_with_timeout(
            download_radar_relay_token_addresses(token_dict))

        self.assertIn("BTC", token_dict)
        self.assertIn("USDT", token_dict)

    @patch("logging.Logger.error")
    @aioresponses()
    def test_download_radar_relay_token_addresses_logs_errors(
        self, error_mock: MagicMock, mocked_api
    ):
        url = RADAR_RELAY_ENDPOINT
        regex_url = re.compile(f"^{url}")
        mocked_api.get(regex_url, status=501)
        token_dict = {}

        self.async_run_with_timeout(
            download_radar_relay_token_addresses(token_dict))

        error_mock.assert_called()

    @aioresponses()
    def test_download_bamboo_relay_token_addresses(self, mocked_api):
        url = BAMBOO_RELAY_ENDPOINT
        regex_url = re.compile(f"^{url}")
        btc_address = "0x0000000000000000000000000000000000000000"
        usdt_address = "0x0000000000000000000000000000000000000001"
        resp = [
            {
                "id": "BTC-USDT",
                "baseTokenAddress": btc_address,
                "quoteTokenAddress": usdt_address,
            }
        ]
        mocked_api.get(regex_url, body=json.dumps(resp))
        mocked_api.get(regex_url, body=json.dumps([]))  # to break the loop
        token_dict = {}

        self.async_run_with_timeout(download_bamboo_relay_token_addresses(token_dict))

        self.assertIn("BTC", token_dict)
        self.assertIn("USDT", token_dict)

    @patch("logging.Logger.error")
    @aioresponses()
    def test_download_bamboo_relay_token_addresses_logs_errors(
        self, error_mock: MagicMock, mocked_api
    ):
        url = BAMBOO_RELAY_ENDPOINT
        regex_url = re.compile(f"^{url}")
        mocked_api.get(regex_url, status=501)
        token_dict = {}

        self.async_run_with_timeout(download_bamboo_relay_token_addresses(token_dict))

        error_mock.assert_called()

    @aioresponses()
    @patch("hummingbot.core.utils.download_token_addresses.open")
    @patch("hummingbot.core.utils.download_token_addresses.json.load")
    def test_download_erc20_token_addresses(
        self, mocked_api, json_load_mock: MagicMock, open_mock: MagicMock
    ):
        for url in [BAMBOO_RELAY_ENDPOINT, RADAR_RELAY_ENDPOINT]:
            regex_url = re.compile(f"^{url}")
            initial_btc_identifier = "0x0000000000000000000000000000000000000000"
            usdt_identifier = "0x0000000000000000000000000000000000000001"
            resp = [
                {
                    "id": "BTC-USDT",
                    "baseTokenAddress": initial_btc_identifier,
                    "quoteTokenAddress": usdt_identifier,
                }
            ]
            mocked_api.get(regex_url, body=json.dumps(resp))
            mocked_api.get(regex_url, body=json.dumps([]))  # to break the loop
        url = DOLOMITE_ENDPOINT
        lrc_identifier = "0x0000000000000000000000000000000000000000"
        subsequent_btc_identifier = "0x0000000000000000000000000000000000000001"
        resp = self.get_dolomite_tokens_mock(
            first_ticker="LRC",
            first_identifier=lrc_identifier,
            second_ticker="BTC",
            second_identifier=subsequent_btc_identifier,
        )
        mocked_api.get(url, body=json.dumps(resp))

        json_load_mock.return_value = {}
        download_erc20_token_addresses()
        open_mock().__enter__().write.assert_called_with(
            json.dumps(
                {"BTC": initial_btc_identifier,
                 "USDT": usdt_identifier,
                 "LRC": lrc_identifier}
            )
        )

    @patch("hummingbot.core.utils.download_token_addresses.open")
    @patch("logging.Logger.error")
    @patch("hummingbot.core.utils.download_token_addresses.json")
    def test_download_erc20_token_addresses_logs_errors(
        self, json_mock: MagicMock, error_mock: MagicMock, __
    ):
        json_mock.load.return_value = None
        download_erc20_token_addresses()

        error_mock.assert_called()
