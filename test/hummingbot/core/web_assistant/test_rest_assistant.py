import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import MagicMock, patch

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSRequest
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase


class RESTAssistantTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()

    @aioresponses()
    async def test_rest_assistant_call_with_pre_and_post_processing(self, mocked_api):
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
        aiohttp_client_session = aiohttp.ClientSession()
        connection = RESTConnection(aiohttp_client_session)
        assistant = RESTAssistant(
            connection=connection,
            throttler=AsyncThrottler(rate_limits=[]),
            rest_pre_processors=pre_processors,
            rest_post_processors=post_processors)
        req = RESTRequest(method=RESTMethod.GET, url=url)

        ret = await (assistant.call(req))
        ret_json = await (ret.json())

        self.assertEqual(resp, ret_json)
        self.assertTrue(pre_processor_ran)
        self.assertTrue(post_processor_ran)
        await aiohttp_client_session.close()

    @patch("hummingbot.core.web_assistant.connections.rest_connection.RESTConnection.call")
    async def test_rest_assistant_authenticates(self, mocked_call):
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

        aiohttp_client_session = aiohttp.ClientSession()
        connection = RESTConnection(aiohttp_client_session)
        assistant = RESTAssistant(connection, throttler=AsyncThrottler(rate_limits=[]), auth=AuthDummy())
        req = RESTRequest(method=RESTMethod.GET, url=url)
        auth_req = RESTRequest(method=RESTMethod.GET, url=url, is_auth_required=True)

        await (assistant.call(req))

        self.assertIsNotNone(call_request)
        self.assertIsNone(call_request.headers)

        await (assistant.call(auth_req))

        self.assertIsNotNone(call_request)
        self.assertIsNotNone(call_request.headers)
        self.assertEqual(call_request.headers, auth_header)
        await aiohttp_client_session.close()

    @patch("hummingbot.core.web_assistant.connections.rest_connection.RESTConnection.call")
    async def test_rate_limit_slot_is_held_while_the_body_is_read(self, mocked_call):
        url = "https://www.test.com/url"
        limit_id = "test_limit"
        throttler = AsyncThrottler(rate_limits=[RateLimit(limit_id=limit_id, limit=1, time_interval=1)])
        completed_while_reading = None

        async def read_body():
            nonlocal completed_while_reading
            completed_while_reading = [task.completed for task in throttler._task_logs]
            return json.dumps({"one": 1}).encode()

        # Headers have arrived, the body has not.
        aiohttp_response = MagicMock()
        aiohttp_response.status = 200
        aiohttp_response.read.side_effect = read_body
        mocked_call.return_value = RESTResponse(aiohttp_response)

        aiohttp_client_session = aiohttp.ClientSession()
        assistant = RESTAssistant(RESTConnection(aiohttp_client_session), throttler=throttler)

        await assistant.execute_request_and_get_response(url=url, throttler_limit_id=limit_id)

        self.assertEqual([False], completed_while_reading)
        self.assertEqual([True], [task.completed for task in throttler._task_logs])
        await aiohttp_client_session.close()

    @aioresponses()
    async def test_execute_request_returns_the_body_read_inside_the_throttler(self, mocked_api):
        url = "https://www.test.com/url"
        resp = {"one": 1}
        mocked_api.get(url, body=json.dumps(resp).encode(), content_type="application/json")

        aiohttp_client_session = aiohttp.ClientSession()
        throttler = AsyncThrottler(rate_limits=[RateLimit(limit_id="test_limit", limit=1, time_interval=1)])
        assistant = RESTAssistant(RESTConnection(aiohttp_client_session), throttler=throttler)

        ret = await assistant.execute_request(url=url, throttler_limit_id="test_limit")

        self.assertEqual(resp, ret)
        await aiohttp_client_session.close()

    @aioresponses()
    async def test_error_response_text_is_still_reported(self, mocked_api):
        url = "https://www.test.com/url"
        mocked_api.get(url, status=400, body="bad request")

        aiohttp_client_session = aiohttp.ClientSession()
        throttler = AsyncThrottler(rate_limits=[RateLimit(limit_id="test_limit", limit=1, time_interval=1)])
        assistant = RESTAssistant(RESTConnection(aiohttp_client_session), throttler=throttler)

        with self.assertRaises(IOError) as error:
            await assistant.execute_request(url=url, throttler_limit_id="test_limit")

        self.assertIn("HTTP status is 400", str(error.exception))
        self.assertIn("bad request", str(error.exception))
        await aiohttp_client_session.close()

    @patch("hummingbot.core.web_assistant.connections.rest_connection.RESTConnection.call")
    async def test_body_is_not_read_when_the_caller_only_needs_headers(self, mocked_call):
        url = "https://www.test.com/url"
        limit_id = "test_limit"
        throttler = AsyncThrottler(rate_limits=[RateLimit(limit_id=limit_id, limit=1, time_interval=1)])

        aiohttp_response = MagicMock()
        aiohttp_response.status = 200
        aiohttp_response.headers = {"Date": "Wed, 21 Oct 2015 07:28:00 GMT"}
        mocked_call.return_value = RESTResponse(aiohttp_response)

        aiohttp_client_session = aiohttp.ClientSession()
        assistant = RESTAssistant(RESTConnection(aiohttp_client_session), throttler=throttler)

        response = await assistant.execute_request_and_get_response(
            url=url, throttler_limit_id=limit_id, read_body=False)

        self.assertEqual("Wed, 21 Oct 2015 07:28:00 GMT", response.headers["Date"])
        aiohttp_response.read.assert_not_called()
        self.assertEqual([True], [task.completed for task in throttler._task_logs])
        await aiohttp_client_session.close()

    @aioresponses()
    async def test_release_frees_the_connection_without_reading_the_body(self, mocked_api):
        url = "https://www.test.com/url"
        mocked_api.get(url, body=json.dumps({"one": 1}).encode())

        aiohttp_client_session = aiohttp.ClientSession()
        connection = RESTConnection(aiohttp_client_session)
        response = await connection.call(RESTRequest(method=RESTMethod.GET, url=url))

        response.release()

        self.assertTrue(response._aiohttp_response.closed)
        await aiohttp_client_session.close()
