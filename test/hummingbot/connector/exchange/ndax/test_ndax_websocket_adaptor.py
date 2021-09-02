import asyncio
import json
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class NdaxWebSocketAdaptorTests(TestCase):

    def test_sending_messages_increment_message_number(self):
        sent_messages = []
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = NdaxWebSocketAdaptor(throttler, websocket=ws)
        payload = {}
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name=CONSTANTS.WS_PING_REQUEST,
                                                                         payload=payload,
                                                                         limit_id=CONSTANTS.WS_PING_ID))
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name=CONSTANTS.WS_PING_REQUEST,
                                                                         payload=payload,
                                                                         limit_id=CONSTANTS.WS_PING_ID))
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name=CONSTANTS.WS_ORDER_BOOK_CHANNEL,
                                                                         payload=payload))
        self.assertEqual(3, len(sent_messages))

        message = json.loads(sent_messages[0])
        self.assertEqual(1, message.get('i'))
        message = json.loads(sent_messages[1])
        self.assertEqual(2, message.get('i'))
        message = json.loads(sent_messages[2])
        self.assertEqual(3, message.get('i'))

    def test_request_message_structure(self):
        sent_messages = []
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = NdaxWebSocketAdaptor(throttler, websocket=ws)
        payload = {"TestElement1": "Value1", "TestElement2": "Value2"}
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name=CONSTANTS.WS_PING_REQUEST,
                                                                         payload=payload,
                                                                         limit_id=CONSTANTS.WS_PING_ID))

        self.assertEqual(1, len(sent_messages))
        message = json.loads(sent_messages[0])

        self.assertEqual(0, message.get('m'))
        self.assertEqual(1, message.get('i'))
        self.assertEqual(CONSTANTS.WS_PING_REQUEST, message.get('n'))
        message_payload = json.loads(message.get('o'))
        self.assertEqual(payload, message_payload)

    def test_receive_message(self):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws = AsyncMock()
        ws.recv.return_value = 'test message'

        adaptor = NdaxWebSocketAdaptor(throttler, websocket=ws)
        received_message = asyncio.get_event_loop().run_until_complete(adaptor.recv())

        self.assertEqual('test message', received_message)

    def test_close(self):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws = AsyncMock()

        adaptor = NdaxWebSocketAdaptor(throttler, websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.close())

        self.assertEquals(1, ws.close.await_count)

    def test_get_payload_from_raw_received_message(self):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws = AsyncMock()
        payload = {"Key1": True,
                   "Key2": "Value2"}
        message = {"m": 1,
                   "i": 1,
                   "n": "Endpoint",
                   "o": json.dumps(payload)}
        raw_message = json.dumps(message)

        adaptor = NdaxWebSocketAdaptor(throttler, websocket=ws)
        extracted_payload = adaptor.payload_from_raw_message(raw_message=raw_message)

        self.assertEqual(payload, extracted_payload)

    def test_get_endpoint_from_raw_received_message(self):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws = AsyncMock()
        payload = {"Key1": True,
                   "Key2": "Value2"}
        message = {"m": 1,
                   "i": 1,
                   "n": "Endpoint",
                   "o": json.dumps(payload)}
        raw_message = json.dumps(message)

        adaptor = NdaxWebSocketAdaptor(throttler, websocket=ws)
        extracted_endpoint = adaptor.endpoint_from_raw_message(raw_message=raw_message)

        self.assertEqual("Endpoint", extracted_endpoint)
