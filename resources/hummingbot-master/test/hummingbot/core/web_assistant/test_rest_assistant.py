import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import patch

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSRequest
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase


class RESTAssistantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_rest_assistant_call_with_pre_and_post_processing(self, mocked_api):
        url = "https://www.test.com/url"
        resp = {"one": 1}
        pre_processor_ran = False
        post_processor_ran = False
        mocked_api.get(url, body=json.dumps(resp).encode())

        class PreProcessor(RESTPreProcessorBase):
            async def pre_process(self, request: RESTRequest) -> RESTRequest:
                nonlocal pre_processor_ran
                pre_processor_ran = True
                return request

        class PostProcessor(RESTPostProcessorBase):
            async def post_process(self, response: RESTResponse) -> RESTResponse:
                nonlocal post_processor_ran
                post_processor_ran = True
                return response

        pre_processors = [PreProcessor()]
        post_processors = [PostProcessor()]
        connection = RESTConnection(aiohttp.ClientSession(loop=self.ev_loop))
        assistant = RESTAssistant(
            connection=connection,
            throttler=AsyncThrottler(rate_limits=[]),
            rest_pre_processors=pre_processors,
            rest_post_processors=post_processors)
        req = RESTRequest(method=RESTMethod.GET, url=url)

        ret = self.async_run_with_timeout(assistant.call(req))
        ret_json = self.async_run_with_timeout(ret.json())

        self.assertEqual(resp, ret_json)
        self.assertTrue(pre_processor_ran)
        self.assertTrue(post_processor_ran)

    @patch("hummingbot.core.web_assistant.connections.rest_connection.RESTConnection.call")
    def test_rest_assistant_authenticates(self, mocked_call):
        url = "https://www.test.com/url"
        resp = {"one": 1}
        call_request: Optional[RESTRequest] = None
        auth_header = {"authenticated": True}

        async def register_request_and_return(request: RESTRequest):
            nonlocal call_request
            call_request = request
            return resp

        mocked_call.side_effect = register_request_and_return

        class AuthDummy(AuthBase):
            async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
                request.headers = auth_header
                return request

            async def ws_authenticate(self, request: WSRequest) -> WSRequest:
                pass

        connection = RESTConnection(aiohttp.ClientSession(loop=self.ev_loop))
        assistant = RESTAssistant(connection, throttler=AsyncThrottler(rate_limits=[]), auth=AuthDummy())
        req = RESTRequest(method=RESTMethod.GET, url=url)
        auth_req = RESTRequest(method=RESTMethod.GET, url=url, is_auth_required=True)

        self.async_run_with_timeout(assistant.call(req))

        self.assertIsNotNone(call_request)
        self.assertIsNone(call_request.headers)

        self.async_run_with_timeout(assistant.call(auth_req))

        self.assertIsNotNone(call_request)
        self.assertIsNotNone(call_request.headers)
        self.assertEqual(call_request.headers, auth_header)
