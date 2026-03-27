import asyncio
import json
import unittest
from typing import Any, Dict

import pandas as pd
from aioresponses import aioresponses

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)


class ArchitectPerpetualWebUtilsTest(unittest.TestCase):
    @staticmethod
    def rest_time_mock_response() -> Dict[str, Any]:
        return {
            "status": "OK",
            "timestamp": "2026-01-10T10:55:13.151818970Z"
        }

    def test_get_rest_url_for_endpoint(self) -> None:
        endpoint = "/test-endpoint"
        url = web_utils.public_rest_url(endpoint, domain=CONSTANTS.SANDBOX_DOMAIN)
        self.assertEqual(f"{CONSTANTS.REST_URL_BASES[CONSTANTS.SANDBOX_DOMAIN]}/test-endpoint", url)

    @aioresponses()
    def test_get_current_server_time(self, api_mock) -> None:
        url = web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_ENDPOINT, domain=CONSTANTS.SANDBOX_DOMAIN)
        data: Dict[str, Any] = self.rest_time_mock_response()

        api_mock.get(url=url, status=200, body=json.dumps(data))

        time = asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(
                web_utils.get_current_server_time(domain=CONSTANTS.SANDBOX_DOMAIN), 1
            )
        )

        self.assertEqual(pd.Timestamp(data["timestamp"]).timestamp(), time)
