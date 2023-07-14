import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils import (
    CoinbaseAdvancedTradeWSSMessage,
    PipelineMessageItem,
    PipelineMessageProcessor,
    build_api_factory,
    build_api_factory_without_time_synchronizer_pre_processor,
    create_throttler,
    endpoint_from_url,
    get_current_server_time_ms,
    get_current_server_time_s,
    get_timestamp_from_exchange_time,
    private_rest_url,
    public_rest_url,
    set_exchange_time_from_timestamp,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

# import requests
# from bs4 import BeautifulSoup


class CoinbaseAdvancedTradeUtilTestCases(IsolatedAsyncioWrapperTestCase):

    # def test_connector_uptodate_changelog(self):
    #     url = CONSTANTS.CHANGELOG_URL
    #     response = requests.get(url)
    #     soup = BeautifulSoup(response.text, 'html.parser')
    #
    #     # Assuming the date is always in a header tag (e.g., <h3>), and is the first one on the page.
    #     date = re.match(r'(\d{4}-[A-Z]{3}-\d{2})', soup.find('h3').text)
    #     self.assertEqual(date.group(0), CONSTANTS.LATEST_UPDATE)
    #     page_hash = hashlib.md5(response.text.encode()).hexdigest()
    #     self.assertEqual(page_hash, CONSTANTS.CHANGELOG_HASH)

    def test_public_rest_url(self):
        # Test default domain
        self.assertEqual(
            public_rest_url('/test'),
            CONSTANTS.REST_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + '/test'
        )

        # Test custom domain
        self.assertEqual(
            public_rest_url('/test', domain='us'),
            CONSTANTS.REST_URL.format(domain='us') + '/test'
        )

        # Test signin url endpoints
        for endpoint in CONSTANTS.SIGNIN_ENDPOINTS:
            self.assertEqual(
                public_rest_url(endpoint),
                CONSTANTS.SIGNIN_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + endpoint
            )

    def test_private_rest_url(self):
        # Similar to the public_rest_url, just replace the function call
        self.assertEqual(
            private_rest_url('/test'),
            CONSTANTS.REST_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + '/test'
        )

        # Test custom domain
        self.assertEqual(
            private_rest_url('/test', domain='us'),
            CONSTANTS.REST_URL.format(domain='us') + '/test'
        )

        # Test signin url endpoints
        for endpoint in CONSTANTS.SIGNIN_ENDPOINTS:
            self.assertEqual(
                private_rest_url(endpoint),
                CONSTANTS.SIGNIN_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + endpoint
            )

    def test_create_throttler(self):
        throttler = create_throttler()
        self.assertIsInstance(throttler, AsyncThrottler)

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils"
           ".create_throttler", return_value=Mock())
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils"
           ".get_current_server_time_s")
    def test_build_api_factory(self, mock_get_current_server_time_s, mock_create_throttler, mock_init):
        mock_get_current_server_time_s.return_value = 123456
        create_throttler()
        build_api_factory()
        mock_create_throttler.assert_called_once()
        mock_init.assert_called_once_with(
            throttler=mock_create_throttler.return_value,
            auth=None,
            rest_pre_processors=[ANY]

        )

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    def test_build_api_factory_without_time_synchronizer_pre_processor(self, mock_factory):
        throttler = Mock()
        build_api_factory_without_time_synchronizer_pre_processor(throttler)
        mock_factory.assert_called_once_with(throttler=throttler)

    @patch('hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils'
           '.get_current_server_time_s')
    async def test_get_current_server_time_ms(self, mock_get_time_s):
        mock_get_time_s.return_value = 1
        result = await get_current_server_time_ms()
        self.assertEqual(result, 1000)

    def test_get_timestamp_from_exchange_time(self):
        # Test with seconds
        expected_seconds = 1683808496.789012
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 's'), expected_seconds)

        # Test with milliseconds
        expected_milliseconds = expected_seconds * 1000
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'ms'),
                         expected_milliseconds)

        # Test with long string
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.7890123456+00:00', 'ms'),
                         expected_milliseconds)

        # Test with different units
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'seconds'),
                         expected_seconds)
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'second'),
                         expected_seconds)
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'milliseconds'),
                         expected_milliseconds)
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'millisecond'),
                         expected_milliseconds)

    @patch(
        'hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils'
        '.build_api_factory_without_time_synchronizer_pre_processor',
        new_callable=Mock)
    @patch('hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils'
           '.public_rest_url')
    async def test_get_current_server_time_s(self, mock_public_rest_url, mock_api_factory):
        # Prepare Mocks
        mock_public_rest_url.return_value = 'mock_url'
        mock_rest_assistant = AsyncMock()
        mock_rest_assistant.execute_request.return_value = {
            "data": {"iso": "2007-04-05T14:30Z", "epoch": 1175783400}}

        async def get_rest_assistant():
            return mock_rest_assistant

        mock_api_factory.return_value.get_rest_assistant = get_rest_assistant

        # Run Test
        server_time = await get_current_server_time_s()

        # Assertions
        mock_public_rest_url.assert_called_with(path_url=CONSTANTS.SERVER_TIME_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
        mock_rest_assistant.execute_request.assert_called_with(
            url='mock_url',
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SERVER_TIME_EP,
        )
        self.assertEqual(server_time, 1175783400)

    def test_endpoint_from_url(self):
        # Test with a variety of URLs
        self.assertEqual(endpoint_from_url("https://api.coinbase.com/test"), "/test")
        with self.assertRaises(ValueError):
            endpoint_from_url("https://api.coinbase.us")
        with self.assertRaises(ValueError):
            self.assertEqual(endpoint_from_url("https://api.coinbase.us/test", "com"), "/test")
        self.assertEqual(endpoint_from_url("https://api.coinbase.us/test", "us"), "/test")

    def test_set_exchange_time_from_timestamp(self):
        # Test with a variety of timestamps and units
        self.assertEqual(set_exchange_time_from_timestamp(1683808496.789012, "s"), '2023-05-11T12:34:56.789012Z')
        self.assertEqual(set_exchange_time_from_timestamp(1683808496789.012, "ms"), '2023-05-11T12:34:56.789012Z')


class TestPipelineMessageProcessor(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        self.mock_preprocessor = AsyncMock(return_value=[{"item": 0}, {"item": 1}])
        mock_logger = MagicMock()
        mock_logger.error = MagicMock()
        self.mock_logger = MagicMock(return_value=mock_logger)
        self.processor = PipelineMessageProcessor(self.mock_preprocessor, self.mock_logger)
        self.wss_message: CoinbaseAdvancedTradeWSSMessage = CoinbaseAdvancedTradeWSSMessage(
            channel="market_trades",
            client_id="",
            timestamp="2023-02-09T20:19:35.39625135Z",
            sequence_num=0,
            events=()
        )

    async def asyncTearDown(self):
        await self.processor.stop()

    def test_queue_property_init(self):
        self.assertIs(self.processor._message_queue, None)
        self.assertIs(self.processor._message_queue_task, None)
        self.assertIs(self.processor._preprocessor, self.mock_preprocessor)
        self.assertIs(self.processor.logger, self.mock_logger)
        self.assertFalse(self.processor._is_started)

    @patch('asyncio.create_task')
    async def test_start(self, mock_create_task):
        await self.processor.start()
        self.assertTrue(self.processor._is_started)
        self.assertIsInstance(self.processor._message_queue, asyncio.Queue)
        self.assertIsNotNone(self.processor._message_queue_task)
        self.assertIs(self.processor._preprocessor, self.mock_preprocessor)
        self.assertIs(self.processor.logger, self.mock_logger)
        self.assertIn("PipelineMessageProcessor._preprocess_messages", repr(mock_create_task.call_args_list))
        mock_create_task.assert_called_once()

        # The pipeline is waiting for messages
        self.mock_preprocessor.assert_not_called()
        self.mock_preprocessor.assert_not_awaited()

        await self.processor.stop()

    async def test_process_messages(self):
        async def mock_preprocessor(message):
            self.assertEqual(message, self.wss_message)
            yield {"item": 0}
            yield {"item": 1}

        self.processor._preprocessor = mock_preprocessor

        await self.processor.start()
        self.assertIs(self.processor._preprocessor, mock_preprocessor)

        # Add an item to the queue so that the _preprocess_messages coroutine has something to process
        out_queue = asyncio.Queue()
        pipeline_message = PipelineMessageItem(self.wss_message, out_queue)
        await self.processor.queue.put(pipeline_message)

        # Sleep for a short while to allow the event loop to run the task
        await asyncio.sleep(0.1)

        # Check if the preprocessor has been called by examining the queue
        self.assertFalse(out_queue.empty())
        self.assertEqual(out_queue.qsize(), 2)
        self.assertEqual({"item": 0}, out_queue.get_nowait())
        self.assertEqual({"item": 1}, out_queue.get_nowait())

        await self.processor.stop()

    async def test_process_messages_with_exception(self):
        async def mock_preprocessor(message):
            self.assertEqual(message, self.wss_message)
            yield ValueError("Test Exception")
            yield {"item": 1}

        self.processor._preprocessor = mock_preprocessor

        await self.processor.start()
        self.assertIs(self.processor._preprocessor, mock_preprocessor)

        # Add an item to the queue so that the _preprocess_messages coroutine has something to process
        out_queue = asyncio.Queue()
        pipeline_message = PipelineMessageItem(self.wss_message, out_queue)
        await self.processor.queue.put(pipeline_message)

        # Sleep for a short while to allow the event loop to run the task
        await asyncio.sleep(0.1)

        # Check if the preprocessor has been called by examining the queue
        self.assertFalse(out_queue.empty())
        self.assertEqual(2, out_queue.qsize())
        self.assertEqual({"item": 1}, out_queue.get_nowait())
        self.error.assert_called_once_with(
            "Exception while processing message: Test exception. Message dropped")

        await self.processor.stop()

    async def test_preprocess_messages_cancelled(self):
        await self.processor.start()
        task = asyncio.create_task(self.processor._preprocess_messages())
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self.mock_logger.error.assert_not_called()

    async def test_preprocess_messages_preprocessor_exception(self):
        expected_exception_msg = 'Test exception'

        class MockAsyncIterator:
            def __init__(self, items, raise_exception=False):
                self.items = items
                self.raise_exception = raise_exception

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.raise_exception:
                    raise Exception(expected_exception_msg)
                try:
                    return self.items.pop(0)
                except IndexError:
                    raise StopAsyncIteration

        def get_mock_async_iterator(message):
            self.assertEqual(message, self.wss_message)
            return MockAsyncIterator([{"item": 0}, {"item": 1}], raise_exception=True)

        self.processor._preprocessor = get_mock_async_iterator

        await self.processor.start()
        out_queue = asyncio.Queue()
        pipeline_message = PipelineMessageItem(self.wss_message, out_queue)
        await self.processor.queue.put(pipeline_message)
        await asyncio.sleep(0.1)
        self.mock_logger.assert_called_once()
        self.mock_logger().error.assert_called_once_with(
            f'Exception while processing message: {expected_exception_msg}. Message dropped')

    @patch('hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_web_utils'
           '.try_except_queue_put', side_effect=asyncio.QueueFull)
    async def test_preprocess_messages_queuefull_exception(self, mock_try_except_queue_put):
        class MockAsyncIterator:
            def __init__(self, items, raise_exception=False):
                self.items = items
                self.raise_exception = raise_exception

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return self.items.pop(0)
                except IndexError:
                    raise StopAsyncIteration

        def get_mock_async_iterator(message):
            self.assertEqual(message, self.wss_message)
            return MockAsyncIterator([{"item": 0}], raise_exception=True)

        self.processor._preprocessor = get_mock_async_iterator
        await self.processor.start()
        out_queue = asyncio.Queue(maxsize=1)
        pipeline_message = PipelineMessageItem(self.wss_message, out_queue)
        await self.processor.queue.put(pipeline_message)
        await out_queue.put('fill queue')
        await asyncio.sleep(0.1)
        self.mock_logger().error.assert_called_once_with('Timeout while waiting to put order into the out queue')

    async def test_stop(self):
        await self.processor.start()
        await self.processor.stop()
        self.assertFalse(self.processor._is_started)
        self.assertTrue(self.processor._message_queue.empty())
        self.assertTrue(self.processor._message_queue_task.cancelled())


if __name__ == "__main__":
    unittest.main()
