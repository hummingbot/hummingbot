import unittest
import asyncio
import conf
from typing import (
    Dict
)
from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth


class BeaxyAuthUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.beaxy_auth: BeaxyAuth = BeaxyAuth(conf.beaxy_api_key, conf.beaxy_secret_key)

    def test_get_auth_session(self):
        result: Dict[str, str] = self.ev_loop.run_until_complete(self.beaxy_auth.generate_auth_dict("GET", "/api/staff"))
        self.assertIsNotNone(result)
