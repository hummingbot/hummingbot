import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_websocket_adaptor import BybitPerpetualWebSocketAdaptor


class BybitPerpetualWebSocketAdaptorTests(TestCase):

    def _raise_asyncio_timeout_exception(self):
        raise asyncio.TimeoutError()

    async def _iterate_messages(self, websocket_adaptor):
        async for message in websocket_adaptor.iter_messages():
            pass

    def test_request_message_structure(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        payload = {"TestElement1": "Value1", "TestElement2": "Value2"}
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(payload=payload))

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]

        self.assertEqual(payload, message)

    def test_close(self):
        ws = AsyncMock()

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.close())

        self.assertEquals(1, ws.close.await_count)

    def test_subscribe_to_order_book_for_two_symbols(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.subscribe_to_order_book(["BTCUSD", "ETHUSD"]))

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]
        expected_message = {"op": "subscribe",
                            "args": ["orderBook_200.100ms.BTCUSD|ETHUSD"]}
        self.assertEqual(expected_message, message)

    def test_subscribe_to_order_book_for_all_symbols(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.subscribe_to_order_book())

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]
        expected_message = {"op": "subscribe",
                            "args": ["orderBook_200.100ms.*"]}
        self.assertEqual(expected_message, message)

    def test_subscribe_to_trades_for_two_symbols(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.subscribe_to_trades(["BTCUSD", "ETHUSD"]))

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]
        expected_message = {"op": "subscribe",
                            "args": ["trade.BTCUSD|ETHUSD"]}
        self.assertEqual(expected_message, message)

    def test_subscribe_to_trades_for_all_symbols(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.subscribe_to_trades())

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]
        expected_message = {"op": "subscribe",
                            "args": ["trade.*"]}
        self.assertEqual(expected_message, message)

    def test_subscribe_to_instruments_info_for_two_symbols(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.subscribe_to_instruments_info(["BTCUSD", "ETHUSD"]))

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]
        expected_message = {"op": "subscribe",
                            "args": ["instrument_info.100ms.BTCUSD|ETHUSD"]}
        self.assertEqual(expected_message, message)

    def test_subscribe_to_instruments_info_for_all_symbols(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        asyncio.get_event_loop().run_until_complete(adaptor.subscribe_to_instruments_info())

        self.assertEqual(1, len(sent_messages))
        message = sent_messages[0]
        expected_message = {"op": "subscribe",
                            "args": ["instrument_info.100ms.*"]}
        self.assertEqual(expected_message, message)

    def test_adaptor_sends_ping_heartbeat_when_receive_times_out(self):
        sent_messages = asyncio.Queue()
        messages_to_receive = asyncio.Queue()
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: sent_messages.put_nowait(sent_message)
        ws.receive_json.side_effect = lambda timeout: (self._raise_asyncio_timeout_exception()
                                                       if sent_messages.empty()
                                                       else messages_to_receive.get())

        adaptor = BybitPerpetualWebSocketAdaptor(websocket=ws)
        task = asyncio.get_event_loop().create_task(self._iterate_messages(adaptor))

        messages_to_receive.put_nowait({"topic": "dummyMessage"})

        sent_message = asyncio.get_event_loop().run_until_complete(sent_messages.get())

        task.cancel()
        try:
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # Ignore the cancelled error
            pass

        expected_message = {"op": "ping"}
        self.assertEqual(expected_message, sent_message)
