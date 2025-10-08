import asyncio
import json
import unittest
from typing import Any, Dict

from aioresponses import aioresponses

from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_constants as CONSTANTS,
    bitget_perpetual_web_utils as web_utils,
)


class BitgetPerpetualWebUtilsTest(unittest.TestCase):
    def rest_time_mock_response(self) -> Dict[str, Any]:
        """
        Get a mock REST response for the server time endpoint.

        :return: A dictionary containing the mock REST response data.
        """
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1688008631614,
            "data": {
                "serverTime": "1688008631614"
            }
        }

    def test_get_rest_url_for_endpoint(self) -> None:
        """
        Test that the correct REST URL is generated for a given endpoint.
        """
        endpoint = "/test-endpoint"
        url = web_utils.public_rest_url(endpoint)
        self.assertEqual("https://api.bitget.com/test-endpoint", url)

    @aioresponses()
    def test_get_current_server_time(self, api_mock) -> None:
        """
        Test that the current server time is correctly retrieved.
        """
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT)
        data: Dict[str, Any] = self.rest_time_mock_response()

        api_mock.get(url=url, status=400, body=json.dumps(data))

        time = asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(
                web_utils.get_current_server_time(), 1
            )
        )

        self.assertEqual(data["requestTime"], time)
