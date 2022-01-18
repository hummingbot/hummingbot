#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import logging
import ujson
from os.path import join, realpath
from typing import Dict, Any
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_utils import rest_response_with_errors
from hummingbot.connector.exchange.gate_io.gate_io_websocket import GateIoWebsocket
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

    async def rest_auth(self) -> Dict[Any, Any]:
        endpoint = CONSTANTS.USER_BALANCES_PATH_URL
        headers = self.auth.get_headers("GET", f"{CONSTANTS.REST_URL_AUTH}/{endpoint}", None)
        http_client = aiohttp.ClientSession()
        response = await http_client.get(f"{CONSTANTS.REST_URL}/{endpoint}", headers=headers)
        await http_client.close()
        return await response.json()

    async def rest_auth_post(self) -> Dict[Any, Any]:
        endpoint = CONSTANTS.ORDER_CREATE_PATH_URL
        http_client = aiohttp.ClientSession()
        order_params = ujson.dumps({
            'currency_pair': 'ETH_BTC',
            'type': 'limit',
            'side': 'buy',
            'amount': '0.00000001',
            'price': '0.0000001',
        })
        headers = self.auth.get_headers("POST", f"{CONSTANTS.REST_URL_AUTH}/{endpoint}", order_params)
        http_status, response, request_errors = await rest_response_with_errors(
            http_client.request(
                method='POST', url=f"{CONSTANTS.REST_URL}/{endpoint}", headers=headers, data=order_params
            )
        )
        await http_client.close()
        return response

    async def ws_auth(self) -> Dict[Any, Any]:
        ws = GateIoWebsocket(self.auth)
        await ws.connect()
        await ws.subscribe(CONSTANTS.USER_BALANCE_ENDPOINT_NAME)
        async for response in ws.on_message():
            if ws.is_subscribed:
                return True
            return False

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        if len(result) == 0 or "currency" not in result[0].keys():
            print(f"Unexpected response for API call: {result}")
        assert "currency" in result[0].keys()

    def test_rest_auth_post(self):
        result = self.ev_loop.run_until_complete(self.rest_auth_post())
        if "message" not in result.keys():
            print(f"Unexpected response for API call: {result}")
        assert "message" in result.keys()
        assert "Your order size 0.00000001 is too small" in result['message']

    def test_ws_auth(self):
        response = self.ev_loop.run_until_complete(self.ws_auth())
        assert response is True
