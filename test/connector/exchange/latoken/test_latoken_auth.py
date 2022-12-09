import asyncio
import unittest
from typing import Any, Dict

import stomper
import ujson

import conf
from hummingbot.connector.exchange.latoken import latoken_constants as CONSTANTS, latoken_web_utils as web_utils
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_web_assistants_factory import LatokenWebAssistantsFactory
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = "com"
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.latoken_api_key
        secret_key = conf.latoken_secret_key
        cls.trading_pair = "BTC-USDT"
        ts = TimeSynchronizer()
        auth = LatokenAuth(api_key, secret_key, ts)
        cls.api_factory = LatokenWebAssistantsFactory(auth=auth)

    async def rest(self, path_url: str) -> Dict[Any, Any]:
        """REST public request"""
        url = web_utils.public_rest_url(path_url=path_url, domain=self.domain)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        request = RESTRequest(method=RESTMethod.GET, url=url, headers=headers, is_auth_required=False)
        client = await self.api_factory.get_rest_assistant()
        response: RESTResponse = await client.call(request)
        return await response.json()

    async def rest_auth(self, path_url: str) -> Dict[Any, Any]:
        """REST private GET request"""
        url = web_utils.private_rest_url(path_url=path_url, domain=self.domain)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        request = RESTRequest(method=RESTMethod.GET, url=url, headers=headers, is_auth_required=True)
        client = await self.api_factory.get_rest_assistant()
        response: RESTResponse = await client.call(request)
        return await response.json()

    async def rest_auth_post(self, json) -> Dict[Any, Any]:
        """REST private POST request (order placement)"""
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.domain)
        method = RESTMethod.POST
        headers = {
            "Content-Type": "application/json" if method == RESTMethod.POST else "application/x-www-form-urlencoded"}
        request = RESTRequest(
            method=method, url=url, data=json, params=None, headers=headers, is_auth_required=True)
        client = await self.api_factory.get_rest_assistant()
        response = await client.call(request)
        return await response.json()

    async def ws_auth(self) -> Dict[Any, Any]:
        """ws private (user account balance request)"""
        listen_key = (await self.rest_auth(CONSTANTS.USER_ID_PATH_URL))["id"]  # this is the getUserId from the github latoken api client library
        client: WSAssistant = await self.api_factory.get_ws_assistant()
        await client.connect(
            ws_url=web_utils.ws_url(self.domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

        msg_out = stomper.Frame()
        msg_out.cmd = "CONNECT"
        msg_out.headers.update({
            "accept-version": "1.1",
            "heart-beat": "0,0"
        })
        connect_request: WSRequest = WSRequest(payload=msg_out.pack(), is_auth_required=True)
        await client.send(connect_request)
        await client.receive()
        path_params = {'user': listen_key}
        msg_subscribe_account = stomper.subscribe(
            CONSTANTS.ACCOUNT_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_ACCOUNT, ack="auto")
        _ = await client.subscribe(request=WSRequest(payload=msg_subscribe_account))

        response = []
        async for ws_response in client.iter_messages():
            msg_in = stomper.Frame()
            data = msg_in.unpack(ws_response.data.decode())
            event_type = int(data['headers']['subscription'].split('_')[0])
            if event_type == CONSTANTS.SUBSCRIPTION_ID_ACCOUNT:
                response.append(ujson.loads(data["body"])["payload"])
                break
        await client.disconnect()
        return response[0]

    async def get_tag_by_id(self, trading_pair):
        """get uuid id for latoken ticker tag"""
        symbol_parts = self.trading_pair.split('-')
        base = symbol_parts[0]
        quote = symbol_parts[1]
        base_request = await self.rest(f"{CONSTANTS.CURRENCY_PATH_URL}/{base}")
        base_id = base_request['id']
        quote_request = await self.rest(f"{CONSTANTS.CURRENCY_PATH_URL}/{quote}")
        quote_id = quote_request['id']
        return base_id, quote_id

    def test_rest_auth(self):
        """REST private request test, by getting user id required for ws auth"""
        result = self.ev_loop.run_until_complete(self.rest_auth(CONSTANTS.USER_ID_PATH_URL))
        if len(result) == 0 or "id" not in result:
            print(f"Unexpected response for API call: {result}")
        assert "id" in result

    def test_rest_auth_post(self):
        new_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )
        base_id, quote_id = self.ev_loop.run_until_complete(self.get_tag_by_id(self.trading_pair))
        # result = self.ev_loop.run_until_complete(self.rest_auth_post(json=payload.JsonPayload({
        #     "baseCurrency": base_id,
        #     "quoteCurrency": quote_id,
        #     "side": "BID",
        #     "condition": "GTC",
        #     "type": "LIMIT",
        #     "clientOrderId": new_order_id,
        #     "price": "10103.19",
        #     "quantity": ".001",
        #     "timestamp": 1568185507
        # }, dumps=ujson.dumps)))

        result = self.ev_loop.run_until_complete(self.rest_auth_post(json={
            "baseCurrency": base_id,
            "quoteCurrency": quote_id,
            "side": "BID",
            "condition": "GTC",
            "type": "LIMIT",
            "clientOrderId": new_order_id,
            "price": "10103.19",
            "quantity": ".001",
            "timestamp": 1568185507
        }))
        if "status" not in result:
            print(f"Unexpected response for API call: {result}")
        assert "status" in result.keys()
        assert "SUCCESS" == result['status']

    def test_rest_auth_post_order_size_too_high(self):
        new_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair="LA-USDT",
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        base_id, quote_id = self.ev_loop.run_until_complete(self.get_tag_by_id(self.trading_pair))
        result = self.ev_loop.run_until_complete(self.rest_auth_post(json={
            "baseCurrency": base_id,
            "quoteCurrency": quote_id,
            "side": "BID",
            "condition": "GTC",
            "type": "LIMIT",
            "clientOrderId": new_order_id,
            "price": "10103.000000000000000000000000019",  # false
            "quantity": "3.21",
            "timestamp": 1568185507
        }))
        if "status" not in result:
            print(f"Unexpected response for API call: {result}")
        assert "status" in result.keys()
        assert "FAILURE" == result['status']
        assert 'VALIDATION_ERROR' == result['error']
        assert 'price' in result['errors']

    def test_ws_auth(self):
        response = self.ev_loop.run_until_complete(self.ws_auth())
        assert isinstance(response, list)
        assert isinstance(response[0], dict)  # be sure to have balance in spot account
        assert "id" in response[0]
