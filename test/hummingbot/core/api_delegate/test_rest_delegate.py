import asyncio
import json
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock

from hummingbot.core.api_delegate.connections.connections_base import (
    RESTConnectionBase
)
from hummingbot.core.api_delegate.data_types import (
    RESTMethod, RESTRequest, RESTResponse
)
from hummingbot.core.api_delegate.rest_delegate import RESTDelegate
from hummingbot.core.api_delegate.rest_post_processors import (
    RESTPostProcessorBase
)
from hummingbot.core.api_delegate.rest_pre_processors import (
    RESTPreProcessorBase
)


class RESTDelegateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_delegate_call_with_pre_and_post_processing(self):
        connection_mock = AsyncMock(spec=RESTConnectionBase)
        url = "https://www.test.com/url"
        resp_body = {"one": 1}
        resp_mock = RESTResponse(
            url=url,
            method=RESTMethod.GET,
            status=200,
            body=json.dumps(resp_body).encode(),
        )
        requests = []

        def mocked_call(r):
            requests.append(r)
            return resp_mock

        connection_mock.call.side_effect = mocked_call
        req_header = "reqHeader"
        resp_header = "respHeader"

        class PreProcessor(RESTPreProcessorBase):
            async def pre_process(self, request: RESTRequest) -> RESTRequest:
                request.headers = req_header
                return request

        class PostProcessor(RESTPostProcessorBase):
            async def post_process(self, response: RESTResponse) -> RESTResponse:
                response.headers = resp_header
                return response

        pre_processors = [PreProcessor()]
        post_processors = [PostProcessor()]
        delegate = RESTDelegate(connection_mock, pre_processors, post_processors)
        req = RESTRequest(method=RESTMethod.GET, url=url)

        ret = self.async_run_with_timeout(delegate.call(req))

        self.assertIsNone(req.headers)  # original request not modified
        self.assertEqual(1, len(requests))

        req = requests[0]

        self.assertEqual(req_header, req.headers)  # modified by pre-processor
        self.assertEqual(resp_body, ret.json())
        self.assertEqual(resp_header, ret.headers)  # modified by the post-processor
