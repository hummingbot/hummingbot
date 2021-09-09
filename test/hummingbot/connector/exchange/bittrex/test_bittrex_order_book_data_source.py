import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source import \
    BittrexAPIOrderBookDataSource


class BittrexOrderBookDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self._finalMessage = 'FinalDummyMessage'

        self.output_queue = asyncio.Queue()

        self.ob_data_source = BittrexAPIOrderBookDataSource(trading_pairs=[self.trading_pair])

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
        "hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source.BittrexAPIOrderBookDataSource"
        "._transform_raw_message"
    )
    def test_listen_for_trades(self, transform_raw_message_mock, mocked_connection, _):
        transform_raw_message_mock.side_effect = lambda arg: arg
        mocked_connection.return_value = self._create_queue_mock()
        self.ws_incoming_messages.put_nowait(
            {
                'nonce': 1630292147820.41,
                'type': 'trade',
                'results': {
                    'deltas': [
                        {
                            'id': 'b25fd775-bc1d-4f83-a82f-ff3022bb6982',
                            'executedAt': '2021-08-30T02:55:47.75Z',
                            'quantity': '0.01000000',
                            'rate': '3197.61663059',
                            'takerSide': 'SELL',
                        }
                    ],
                    'sequence': 1228,
                    'marketSymbol': self.trading_pair,
                }
            }
        )
        self.ws_incoming_messages.put_nowait(self._finalMessage)  # to resume test event
        self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
        self.ev_loop.create_task(self.ob_data_source.listen_for_trades(self.ev_loop, self.output_queue))
        self.ev_loop.run_until_complete(asyncio.wait([self.resume_test_event.wait()], timeout=1))

        queued_msg = self.output_queue.get_nowait()
        self.assertEquals(queued_msg.trading_pair, self.trading_pair)

    @patch("signalr_aio.Connection.start")
    @patch("asyncio.Queue")
    @patch(
        "hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source.BittrexAPIOrderBookDataSource"
        "._transform_raw_message"
    )
    def test_listen_for_order_book_diffs(self, transform_raw_message_mock, mocked_connection, _):
        transform_raw_message_mock.side_effect = lambda arg: arg
        mocked_connection.return_value = self._create_queue_mock()
        self.ws_incoming_messages.put_nowait(
            {
                'nonce': 1630292145769.5452,
                'type': 'delta',
                'results': {
                    'marketSymbol': self.trading_pair,
                    'depth': 25,
                    'sequence': 148887,
                    'bidDeltas': [],
                    'askDeltas': [
                        {
                            'quantity': '0',
                            'rate': '3199.09000000',
                        },
                        {
                            'quantity': '0.36876366',
                            'rate': '3200.78897180',
                        },
                    ],
                },
            }
        )
        self.ws_incoming_messages.put_nowait(self._finalMessage)  # to resume test event
        self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
        self.ev_loop.create_task(self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, self.output_queue))
        self.ev_loop.run_until_complete(asyncio.wait([self.resume_test_event.wait()], timeout=1))

        queued_msg = self.output_queue.get_nowait()
        self.assertEquals(queued_msg.trading_pair, self.trading_pair)
