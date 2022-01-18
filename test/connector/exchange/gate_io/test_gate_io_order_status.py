#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import logging
import os
from os.path import join, realpath
from typing import Dict, Any
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_utils import rest_response_with_errors
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.gate_io_api_key
        secret_key = conf.gate_io_secret_key
        cls.auth = GateIoAuth(api_key, secret_key)
        cls.exchange_order_id = os.getenv("TEST_ORDER_ID")
        cls.trading_pair = os.getenv("TEST_TRADING_PAIR")

    async def fetch_order_status(self) -> Dict[Any, Any]:
        endpoint = CONSTANTS.ORDER_STATUS_PATH_URL.format(id=self.exchange_order_id)
        params = {'currency_pair': self.trading_pair}
        http_client = aiohttp.ClientSession()
        headers = self.auth.get_headers("GET", f"{CONSTANTS.REST_URL_AUTH}/{endpoint}", params)
        http_status, response, request_errors = await rest_response_with_errors(
            http_client.request(method='GET', url=f"{CONSTANTS.REST_URL}/{endpoint}", headers=headers, params=params)
        )
        await http_client.close()
        return response

    def test_order_status(self):
        status_test_ready = all({
                                'id': self.exchange_order_id is not None and len(self.exchange_order_id),
                                'pair': self.trading_pair is not None and len(self.trading_pair),
                                }.values())
        if status_test_ready:
            result = self.ev_loop.run_until_complete(self.fetch_order_status())
            print(f"Response:\n{result}")
