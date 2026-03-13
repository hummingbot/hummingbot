import json
import re
import unittest

from aioresponses import aioresponses

import hummingbot.connector.exchange.backpack.backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils


class BackpackUtilTestCases(unittest.IsolatedAsyncioTestCase):

    def test_public_rest_url(self):
        path_url = "api/v1/test"
        domain = "exchange"
        expected_url = CONSTANTS.REST_URL.format(domain) + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "api/v1/test"
        domain = "exchange"
        expected_url = CONSTANTS.REST_URL.format(domain) + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))

    @aioresponses()
    async def test_get_current_server_time(self, mock_api):
        """Test that the current server time is correctly retrieved from Backpack API."""
        url = web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL, domain="exchange")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # Backpack returns timestamp directly as a number (in milliseconds)
        mock_server_time = 1641312000000

        mock_api.get(regex_url, body=json.dumps(mock_server_time))

        server_time = await web_utils.get_current_server_time()

        self.assertEqual(float(mock_server_time), server_time)
