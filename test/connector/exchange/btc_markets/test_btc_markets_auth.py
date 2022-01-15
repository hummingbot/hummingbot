#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import logging

from os.path import join, realpath
from typing import Dict, Any, List
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.connector.exchange.btc_markets.btc_markets_websocket import BtcMarketsWebsocket
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
import hummingbot.connector.exchange.btc_markets.btc_markets_constants as constants
from hummingbot.connector.exchange.btc_markets.btc_markets_utils import get_ms_timestamp

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.btc_markets_api_key
        secret_key = conf.btc_markets_secret_key
        cls.auth = BtcMarketsAuth(api_key, secret_key)

    async def rest(self) -> Dict[Any, Any]:
        http_client = aiohttp.ClientSession()
        response = await http_client.get(f"{constants.REST_URL}/{constants.TIME_URL}")
        http_client.close()
        return await response.json()

    def test_rest_timestamp(self):
        response = self.ev_loop.run_until_complete(self.rest())
        if 'timestamp' not in response:
            print(f"Auth failed: response: {response}")
            assert False
        else:
            print(f"Auth successful: {response}")
            assert True

    async def rest_auth_balance(self) -> Dict[Any, Any]:
        nonce = get_ms_timestamp()
        authdict = self.auth.generate_auth_dict("GET", f"{constants.ACCOUNTS_URL}/me/balances",
                                                nonce, {})
        headers = self.auth.generate_auth_headers(authdict)
        http_client = aiohttp.ClientSession(headers=headers)
        response = await http_client.get(f"{constants.REST_URL}/{constants.ACCOUNTS_URL}/me/balances")
        http_client.close()
        return await response.json()

    def test_rest_auth_balance(self):
        response = self.ev_loop.run_until_complete(self.rest_auth_balance())
        if 'assetName' not in response[0]:
            print(f"Auth failed: response: {response}")
            assert False
        else:
            print(f"Auth successful: {response}")
            assert True

    async def ws_noauth_marketIds(self, channels: List[str], marketids: List[str]) -> Dict[Any, Any]:
        ws = BtcMarketsWebsocket()
        await ws.connect()
        await ws.subscribe_marketIds(channels, marketids)
        async for response in ws.on_message():
            return response

    def test_ws_noauth_trade_multiplemarketIds(self):
        response = self.ev_loop.run_until_complete(self.ws_noauth_marketIds(["trade"], ["BTC-AUD", "ETH-AUD"]))
        if 'timestamp' not in response:
            print(f"Unexpected response for API call: {response}")
        else:
            print(f"No auth WS multiple market trade event successful: {response}")
            assert True

    def test_ws_noauth_trade_marketIds(self):
        response = self.ev_loop.run_until_complete(self.ws_noauth_marketIds(["trade"], ['BTC-AUD']))
        if 'timestamp' not in response:
            print(f"Unexpected response for API call: {response}")
        else:
            print(f"No auth WS single market trade event successful: {response}")
            assert True

    def test_ws_noauth_tickevent(self):
        response = self.ev_loop.run_until_complete(self.ws_noauth_marketIds(["tick"], ["BTC-AUD"]))
        if 'bestBid' not in response:
            print(f"TickEvent failed: response: {response}")
            assert False
        else:
            print(f"TickEvent successful: {response}")
            assert True

    async def ws_auth(self, channels: List[str], marketids: List[str]) -> Dict[Any, Any]:
        ws = BtcMarketsWebsocket(self.auth)
        await ws.connect()
        await ws.subscribe_marketIds(channels, [marketids])
        async for response in ws.on_message():
            return response


'''
    def test_ws_auth_tradeevent(self):
        response = self.ev_loop.run_until_complete(self.ws_auth(['orderChange'], 'BTC-AUD'))
        if 'tradeId' not in response:
            print(f"TradeEvent failed: response: {response}")
            assert False
        else:
            print(f"TradeEvent successful: {response}")
            assert True
'''
