import asyncio
import json
import unittest
from typing import Awaitable

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.rest_connection import (
    RESTConnection
)
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod, RESTRequest, RESTResponse
)
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_post_processors import (
    RESTPostProcessorBase
)
from hummingbot.core.web_assistant.rest_pre_processors import (
    RESTPreProcessorBase
)


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
        connection = RESTConnection(aiohttp.ClientSession())
        assistant = RESTAssistant(connection, pre_processors, post_processors)
        req = RESTRequest(method=RESTMethod.GET, url=url)

        ret = self.async_run_with_timeout(assistant.call(req))
        ret_json = self.async_run_with_timeout(ret.json())

        self.assertEqual(resp, ret_json)
        self.assertTrue(pre_processor_ran)
        self.assertTrue(post_processor_ran)
