import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.true_perpetual import true_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.true_perpetual.true_perpetual_auth import TruePerpetualAuth
from hummingbot.connector.derivative.true_perpetual.true_perpetual_derivative import TruePerpetualDerivative
from hummingbot.connector.derivative.true_perpetual.true_perpetual_user_stream_data_source import (
    TruePerpetualUserStreamDataSource,
)


class _FakeContent:
    def __init__(self, lines: List[str]):
        self._lines = [line.encode() for line in lines]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)


class _FakeResponse:
    def __init__(self, status: int, lines: List[str], text: str = ""):
        self.status = status
        self.content = _FakeContent(lines)
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TruePerpetualUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.connector = TruePerpetualDerivative(
            true_perpetual_api_key="tbk_test",
            true_perpetual_api_secret="tbs_test",
            trading_pairs=["BTC-USDC"],
            trading_required=False,
            domain=CONSTANTS.DOMAIN,
        )
        self.connector._time_synchronizer.add_time_offset_ms_sample(0)
        self.auth = TruePerpetualAuth(api_key="tbk_test", api_secret="tbs_test", time_provider=self.connector._time_synchronizer)
        self.data_source = TruePerpetualUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=CONSTANTS.DOMAIN,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _session_with(self, response: _FakeResponse) -> MagicMock:
        session = MagicMock()
        session.closed = False
        session.get = MagicMock(return_value=response)
        session.close = AsyncMock()
        return session

    def _account_payload(self):
        return {
            "account": {"equityUsd": "8553.8", "freeCollateralUsd": "7400.1", "marginUsed": "1153.7"},
            "positionsOk": True,
            "positions": [{"market": "BTCUSDC", "size": "0.01", "entry_price": "80000", "unrealized_pnl": "5", "leverage": "5"}],
        }

    def test_last_recv_time_starts_at_zero(self):
        self.assertEqual(0.0, self.data_source.last_recv_time)

    async def test_consume_stream_queues_account_events_and_skips_housekeeping(self):
        lines = [
            "event: ready\n",
            'data: {"ok":true}\n',
            "\n",
            "event: heartbeat\n",
            'data: {"ts":1}\n',
            "\n",
            ": a comment line\n",
            "event: account\n",
            f"data: {json.dumps(self._account_payload())}\n",
            "\n",
            "event: warning\n",
            'data: {"code":"stale"}\n',
            "\n",
            "event: bye\n",
            'data: {"reason":"lifetime"}\n',
            "\n",
        ]
        session = self._session_with(_FakeResponse(200, lines))
        output: asyncio.Queue = asyncio.Queue()
        with patch.object(self.data_source, "_get_session", AsyncMock(return_value=session)):
            await self.data_source._consume_stream(output)

        self.assertEqual(2, output.qsize())
        first = output.get_nowait()
        self.assertEqual("account", first["event"])
        self.assertEqual("8553.8", first["data"]["account"]["equityUsd"])
        second = output.get_nowait()
        self.assertEqual("warning", second["event"])
        self.assertGreater(self.data_source.last_recv_time, 0)
        self.assertTrue(self._is_logged("INFO", "TRUE account stream reached its lifetime; reconnecting."))

        call = session.get.call_args
        self.assertEqual("https://app.truefinance.ai/api/bot/v1/stream", call.args[0])
        headers = call.kwargs["headers"]
        self.assertEqual("tbk_test", headers["X-TRUE-KEY"])
        self.assertIn("X-TRUE-SIGN", headers)
        self.assertEqual("text/event-stream", headers["Accept"])

    async def test_consume_stream_ignores_malformed_json(self):
        lines = ["event: account\n", "data: {not json\n", "\n", "event: account\n", 'data: {"account":{"equityUsd":"1"}}\n', "\n"]
        session = self._session_with(_FakeResponse(200, lines))
        output: asyncio.Queue = asyncio.Queue()
        with patch.object(self.data_source, "_get_session", AsyncMock(return_value=session)):
            with self.assertRaises(ConnectionError):
                await self.data_source._consume_stream(output)
        self.assertEqual(1, output.qsize())
        self.assertEqual("1", output.get_nowait()["data"]["account"]["equityUsd"])

    async def test_consume_stream_raises_on_http_error(self):
        session = self._session_with(_FakeResponse(401, [], text='{"ok":false,"error":"invalid_key"}'))
        with patch.object(self.data_source, "_get_session", AsyncMock(return_value=session)):
            with self.assertRaises(IOError) as context:
                await self.data_source._consume_stream(asyncio.Queue())
        self.assertIn("HTTP 401", str(context.exception))
        self.assertIn("invalid_key", str(context.exception))

    async def test_consume_stream_raises_when_server_closes(self):
        session = self._session_with(_FakeResponse(200, ["event: ready\n", "data: {}\n"]))
        with patch.object(self.data_source, "_get_session", AsyncMock(return_value=session)):
            with self.assertRaises(ConnectionError):
                await self.data_source._consume_stream(asyncio.Queue())

    async def test_listen_for_user_stream_reconnects_after_error(self):
        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)
            if len(sleep_calls) >= 2:
                raise asyncio.CancelledError()

        consume = AsyncMock(side_effect=[IOError("boom"), ConnectionError("closed"), asyncio.CancelledError()])
        with patch.object(self.data_source, "_consume_stream", consume), patch.object(self.data_source, "_sleep", fake_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source.listen_for_user_stream(asyncio.Queue())
        self.assertEqual([self.data_source.RECONNECT_DELAY, self.data_source.RECONNECT_DELAY], sleep_calls)
        self.assertTrue(self._is_logged("WARNING", "TRUE account stream interrupted (boom). Reconnecting in 5 s..."))

    async def test_listen_for_user_stream_propagates_cancellation(self):
        with patch.object(self.data_source, "_consume_stream", AsyncMock(side_effect=asyncio.CancelledError())):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source.listen_for_user_stream(asyncio.Queue())

    async def test_get_session_reuses_open_session(self):
        first = await self.data_source._get_session()
        second = await self.data_source._get_session()
        self.assertIs(first, second)
        await self.data_source.stop()
        self.assertIsNone(self.data_source._session)
        self.assertTrue(first.closed)

    async def test_websocket_assistant_is_not_used(self):
        with self.assertRaises(NotImplementedError):
            await self.data_source._connected_websocket_assistant()
        await self.data_source._subscribe_channels(MagicMock())
