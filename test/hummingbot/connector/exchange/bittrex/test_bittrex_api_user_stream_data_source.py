import asyncio
import base64
import json
import unittest

from unittest.mock import AsyncMock, patch

import zlib


from hummingbot.connector.exchange.bittrex.bittrex_api_user_stream_data_source import \
    BittrexAPIUserStreamDataSource
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth


class BittrexAPIUserStreamDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.secret_key = "someSecret"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self._finalMessage = {"FinalDummyMessage": None}

        self.output_queue = asyncio.Queue()

        self.us_data_source = BittrexAPIUserStreamDataSource(
            bittrex_auth=BittrexAuth(self.api_key, self.secret_key),
            trading_pairs=[self.trading_pair],
        )

    def _create_queue_mock(self):
        queue = AsyncMock()
        queue.get.side_effect = self._get_next_ws_received_message
        return queue

    async def _get_next_ws_received_message(self):
        message = await self.ws_incoming_messages.get()
        if message == self._finalMessage:
            self.resume_test_event.set()
        return message

    @patch("signalr_aio.Connection.start")
    @patch("asyncio.Queue")
    @patch(
        "hummingbot.connector.exchange.bittrex.bittrex_api_user_stream_data_source.BittrexAPIUserStreamDataSource"
        "._transform_raw_message"
    )
    @patch(
        "hummingbot.connector.exchange.bittrex.bittrex_api_user_stream_data_source.BittrexAPIUserStreamDataSource"
        ".authenticate"
    )
    def test_listen_for_user_stream_re_authenticates(
        self, authenticate_mock, transform_raw_message_mock, mocked_connection, _
    ):
        auths_count = 0

        async def check_for_auth(*args, **kwargs):
            nonlocal auths_count
            auths_count += 1

        authenticate_mock.side_effect = check_for_auth
        transform_raw_message_mock.side_effect = lambda arg: arg
        mocked_connection.return_value = self._create_queue_mock()
        self.ws_incoming_messages.put_nowait(
            {
                "event_type": "heartbeat",
                "content": None,
                "error": None,
            }
        )
        self.ws_incoming_messages.put_nowait(
            {
                "event_type": "re-authenticate",
                "content": None,
                "error": None,
            }
        )
        self.ws_incoming_messages.put_nowait(self._finalMessage)  # to resume test event

        self.ev_loop.create_task(self.us_data_source.listen_for_user_stream(self.ev_loop, self.output_queue))
        self.ev_loop.run_until_complete(asyncio.wait([self.resume_test_event.wait()], timeout=1000))

        self.assertEqual(auths_count, 2)

    def test_transform_raw_execution_message(self):

        execution_message = {
            "accountId": "testAccount",
            "sequence": "1001",
            "deltas": [{
                "id": "1",
                "marketSymbol": f"{self.base_asset}{self.quote_asset}",
                "executedAt": "12-03-2021 6:17:16",
                "quantity": "0.1",
                "rate": "10050",
                "orderId": "EOID1",
                "commission": "10",
                "isTaker": False
            }]
        }

        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        compressor.compress(json.dumps(execution_message).encode())
        encoded_execution_message = base64.b64encode(compressor.flush())

        message = {
            "M": [{
                "M": "execution",
                "A": [encoded_execution_message.decode()]
            }
            ]
        }

        transformed_message = self.us_data_source._transform_raw_message(json.dumps(message))

        self.assertEqual("execution", transformed_message["event_type"])
        self.assertEqual(execution_message, transformed_message["content"])
