import asyncio
import json
import re
from typing import Awaitable
from unittest import TestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.ciex import ciex_constants as CONSTANTS, ciex_web_utils as web_utils


class CiexWebUtilsTests(TestCase):

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_current_server_time(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.CIEX_TIME_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "serverTime": 1660677730340,
            "timezone": "GMT+08:00",
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        server_time = self.async_run_with_timeout(web_utils.get_current_server_time())

        self.assertEqual(resp["serverTime"], server_time)
