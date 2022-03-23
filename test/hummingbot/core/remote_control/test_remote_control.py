import asyncio
from copy import deepcopy
import json
import multiprocessing as mp
import time
from unittest import TestCase
from unittest.mock import patch, AsyncMock

from aioresponses import aioresponses

from websockets.exceptions import (
    ConnectionClosed,
    InvalidStatusCode,
    InvalidMessage,
)
from typing import (
    Awaitable,
    List,
)

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.event.events import RemoteCmdEvent
from hummingbot.core.remote_control.remote_command_executor import RemoteCommandExecutor
from hummingbot.script.script_base import ScriptBase

from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class DummyScriptIterator:
    def __init__(self, queue = None):
        self._message_queue = queue

    def process_remote_command_event(self, evt):
        if self._message_queue:
            self._message_queue.put(evt)
        return True


class RemoteControlTest(TestCase):
    level = 0
    log_records = []

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls._patcher = patch("aiohttp.client.URL")

    def setUp(self) -> None:
        super().setUp()

        self.log_records: List = []
        self.received_messages: int = 0
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())

        self.remote_cmds = RemoteCommandExecutor.get_instance()
        self.app = HummingbotApplication()
        self.global_config_backup = deepcopy(global_config_map)
        self.remote_url = "ws://localhost:10073/wss"

        global_config_map["remote_commands_enabled"].value = True
        global_config_map["remote_commands_api_key"].value = "someAPIKey"
        global_config_map["remote_commands_ws_url"].value = self.remote_url

        self.app.logger().setLevel(1)
        self.app.logger().addHandler(self)

        self.remote_cmds.logger().setLevel(1)
        self.remote_cmds.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.remote_cmds.stop()
        self._reset_global_config()
        RemoteCommandExecutor._rce_shared_instance = None
        self.app.remote_command_executor = None
        self.remote_cmds._hb._script_iterator = None
        self.app._script_iterator = None
        super().tearDown()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patcher.stop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    def _reset_global_config(self):
        for key, value in self.global_config_backup.items():
            global_config_map[key] = value

    async def _wait_til_ready(self):
        while True:
            if self.remote_cmds.started:
                break
            await asyncio.sleep(1.0)

    async def _wait_til_stopped(self):
        while True:
            if not self.remote_cmds.started:
                break
            await asyncio.sleep(1.0)

    def _rce_setup(self):
        websocket_mock = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_text_message(websocket_mock, self._get_ignored_event())
        return websocket_mock

    def _remote_cmds_start_wait_ready(self):
        self.app._initialize_remote_command_executor()
        self.remote_cmds.start()
        self.async_run_with_timeout(self._wait_til_ready(), timeout=2)

    def _remote_cmds_start_wait_stopped(self, websocket_mock, wait_for_delivered=True, wait_for_close=True):
        if wait_for_delivered:
            self.mocking_assistant.run_until_all_text_messages_delivered(websocket_mock)
        if wait_for_close:
            closed_callback_event = asyncio.Event()
            websocket_mock.close.side_effect = lambda: closed_callback_event.set()
        self.remote_cmds.stop()
        self.async_run_with_timeout(self._wait_til_stopped(), timeout=2)
        if wait_for_close:
            self.async_run_with_timeout(closed_callback_event.wait(), timeout=2)

    def _remote_cmds_start_and_stop_after_messages(self, websocket_mock):
        self._remote_cmds_start_wait_ready()
        self._remote_cmds_start_wait_stopped(websocket_mock)

    def _remote_cmds_start_and_stop_nowait_delivered(self, websocket_mock):
        self._remote_cmds_start_wait_ready()
        self._remote_cmds_start_wait_stopped(websocket_mock, wait_for_delivered=False)

    def _setup_script(self):
        script_base = ScriptBase()
        script_parent_queue = mp.Queue()
        script_child_queue = mp.Queue()
        script_base.assign_init(script_parent_queue, script_child_queue, 0.0)
        self.remote_cmds._hb._script_iterator = DummyScriptIterator(queue=script_parent_queue)
        return script_base

    def _get_ignored_event(self):
        return json.dumps({"timestamp_event": int(time.time()), "event_descriptor": "ignored event"})

    def _ws_send_json(self, websocket_mock, data_dict):
        self.mocking_assistant.add_websocket_text_message(
            websocket_mock,
            json.dumps(data_dict))

    def _dummy_rest_responses(self, mock_api):
        for x in range(20):
            mock_api.get(r".*", body=json.dumps({}))

    def _raise_exception(self, exception_class):
        raise exception_class

    def _raise_close_exception(self):
        raise ConnectionClosed(500, 'Mock Close Test')

    def _raise_invalid_status_exception(self):
        raise InvalidStatusCode(500)

    def _raise_invalid_apikey_exception(self):
        raise InvalidStatusCode(401)

    # BEGIN Tests

    def test_remote_commands_disconnect_handles_none(self):
        self.remote_cmds._client = None
        self.assertTrue(self.remote_cmds._client is None)
        self.async_run_with_timeout(self.remote_cmds.disconnect(), timeout=2)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_starts(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self._ws_send_json(ws_connect_mock.return_value,
                           {"timestamp_event": 1234567891, "event_descriptor": "help"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.assertEqual(hash(self.app.remote_command_executor._hb), hash(self.remote_cmds._hb))
        self.assertTrue(self._is_logged("INFO", "Starting Remote Command Executor."))
        self.assertTrue(self._is_logged("INFO", "Remote Command Executor is listening."))
        self.assertEqual(1234567891, self.remote_cmds.last_event_received.timestamp_event)
        self.assertTrue(self.remote_cmds.started is False)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_converts_string_to_json(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self.mocking_assistant.add_websocket_text_message(
            ws_connect_mock.return_value,
            "dummy message")

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.assertEqual("dummy message", self.remote_cmds.last_event_received.command)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_does_not_convert_bad_string_to_json(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self.mocking_assistant.add_websocket_text_message(
            ws_connect_mock.return_value,
            "!dummy message&()")

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.assertEqual(None, self.remote_cmds.last_event_received)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_does_not_process_duplicate_timestamps(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1"})

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 2"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.assertEqual("test 1", self.remote_cmds.last_event_received.event_descriptor)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_skips_unmatched(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        self.remote_cmds._routing_name = "donotmatch"
        ws_connect_mock.return_value = self._rce_setup()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.assertEqual(None, self.remote_cmds.last_event_received)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_translates_commands(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        self.remote_cmds._cmd_translate_dict = {
            "oldname": "newname"
        }
        ws_connect_mock.return_value = self._rce_setup()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1",
                           "command": "oldname"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.assertEqual("newname", self.remote_cmds.last_event_received.command)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    @patch('hummingbot.client.hummingbot_application.HummingbotApplication._handle_command')
    @patch('hummingbot.core.remote_control.remote_command_executor.RemoteCommandExecutor._finish_processing_event_hook')
    def test_remote_commands_enabled_commands(self, mock_api, handle_event_done_mock, handle_cmd_mock, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()
        handle_cmd_event = asyncio.Event()
        done_callback_event = asyncio.Event()
        handle_cmd_mock.side_effect = lambda evt: handle_cmd_event.set()
        handle_event_done_mock.side_effect = lambda: done_callback_event.set()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1",
                           "command": "balance"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)
        self.async_run_with_timeout(done_callback_event.wait())
        self.async_run_with_timeout(handle_cmd_event.wait())

        self.assertEqual("test 1", self.remote_cmds.last_event_received.event_descriptor)
        self.assertTrue(handle_cmd_event.is_set())

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    @patch('hummingbot.client.hummingbot_application.HummingbotApplication._handle_command')
    def test_remote_commands_disabled_commands(self, mock_api, handle_cmd_mock, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        handle_cmd_disabled_event = asyncio.Event()

        ws_connect_mock.return_value = self._rce_setup()
        handle_cmd_mock.side_effect = lambda evt: handle_cmd_disabled_event.set()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1",
                           "command": "connect"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)
        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout(handle_cmd_disabled_event.wait(), timeout=1)

        self.assertEqual("test 1", self.remote_cmds.last_event_received.event_descriptor)
        self.assertFalse(handle_cmd_disabled_event.is_set())

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_no_messages(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        task = asyncio.get_event_loop().create_task(
            self.remote_cmds.listen_loop())

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

        self._remote_cmds_start_wait_stopped(ws_connect_mock.return_value, wait_for_delivered=False, wait_for_close=False)

        self.assertEqual(self.remote_cmds.last_event_received, None)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_inner_recv_timeout(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        self.remote_cmds._ws_timeout = 0.1
        done_callback_event = asyncio.Event()
        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.ping.side_effect = lambda: done_callback_event.set()

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout(self.remote_cmds.listen_loop(), timeout=0.5)

        self.assertEqual(self.remote_cmds.last_event_received, None)
        self.async_run_with_timeout(done_callback_event.wait(), timeout=0.5)

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_ping_timeout(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        self.remote_cmds._ws_timeout = 0.1
        done_callback_event = asyncio.Event()
        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.close.side_effect = lambda: done_callback_event.set()
        ws_connect_mock.return_value.ping.side_effect = NetworkMockingAssistant.async_partial(
            self.mocking_assistant._get_next_websocket_text_message, ws_connect_mock.return_value
        )

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout(self.remote_cmds.listen_loop(), timeout=0.5)

        self.assertEqual(self.remote_cmds.last_event_received, None)
        self.async_run_with_timeout(done_callback_event.wait(), timeout=0.5)
        self.assertTrue(self._is_logged("WARNING", "WebSocket ping timed out. Going to reconnect..."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    @patch('hummingbot.core.remote_control.remote_command_executor.RemoteCommandExecutor._finish_processing_event_hook')
    def test_remote_commands_processing_error(self, mock_api, handle_event_done_mock, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        self.remote_cmds._hb._script_iterator = True
        done_callback_event = asyncio.Event()
        ws_connect_mock.return_value = self._rce_setup()
        handle_event_done_mock.side_effect = lambda: done_callback_event.set()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1",
                           "command": "balance"})

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)
        self.async_run_with_timeout(done_callback_event.wait(), timeout=1)

        self.assertTrue(self._is_logged("ERROR",
                                        ("Remote Command Executor error: "
                                         "'bool' object has no attribute 'process_remote_command_event'")))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_ws_close_exception(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.recv.side_effect = lambda: self._raise_close_exception()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": int(time.time()),
                           "event_descriptor": "dummy message"})

        self._remote_cmds_start_and_stop_nowait_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("INFO", "Starting Remote Command Executor."))
        self.assertTrue(self._is_logged("INFO", "Remote Command Executor is listening."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_ws_invalid_status_url(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)

        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.recv.side_effect = lambda: self._raise_invalid_status_exception()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": int(time.time()),
                           "event_descriptor": "dummy message"})

        self._remote_cmds_start_and_stop_nowait_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Error connecting to websocket, invalid URL, cannot continue."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_ws_invalid_status_apikey(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)

        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.recv.side_effect = lambda: self._raise_invalid_apikey_exception()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": int(time.time()),
                           "event_descriptor": "dummy message"})

        self._remote_cmds_start_and_stop_nowait_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Error connecting to websocket, invalid API key, cannot continue."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_ws_invalid_message(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.recv.side_effect = lambda: self._raise_exception(InvalidMessage)

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": int(time.time()),
                           "event_descriptor": "dummy message"})

        self._remote_cmds_start_and_stop_nowait_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Error connecting to websocket, sleeping 10."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_ws_general_error(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()
        ws_connect_mock.return_value.recv.side_effect = lambda: self._raise_exception(Exception)

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": int(time.time()),
                           "event_descriptor": "dummy message"})

        self._remote_cmds_start_and_stop_nowait_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Unexpected error in websocket, sleeping 20."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_broadcast_success(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self._remote_cmds_start_wait_ready()

        self.remote_cmds.broadcast(RemoteCmdEvent(event_descriptor='test broadcast', timestamp_received=12345678999))

        self._remote_cmds_start_wait_stopped(ws_connect_mock.return_value, wait_for_delivered=False)

        sent_msgs = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_msgs))

        broadcasted_evt = RemoteCmdEvent(event_descriptor="dummy broadcast")

        if len(sent_msgs) == 1:
            broadcasted_evt = RemoteCmdEvent.from_json_data(json.loads(sent_msgs[0]))

        self.assertEqual(12345678999, broadcasted_evt.timestamp_received)
        self.assertEqual("test broadcast", broadcasted_evt.event_descriptor)

    # @patch('websockets.connect', new_callable=AsyncMock)
    # def test_remote_commands_broadcast_failure(self, ws_connect_mock):
    #     ws_connect_mock.return_value = self._rce_setup()

    #     self._remote_cmds_start_wait_ready()
    #     self.remote_cmds.broadcast("")
    #     self._remote_cmds_start_wait_stopped(ws_connect_mock.return_value, wait_for_delivered=False)

    #     sent_msgs = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)

    #     self.assertEqual(0, len(sent_msgs))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_broadcast_failure(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self._remote_cmds_start_wait_ready()
        self.remote_cmds.broadcast("")
        self._remote_cmds_start_wait_stopped(ws_connect_mock.return_value, wait_for_delivered=False)

        sent_msgs = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertEqual(0, len(sent_msgs))
        self.assertTrue(self._is_logged("WARNING", "Remote Command Executor can only broadcast RemoteCmdEvent objects."))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_emit_failure(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()

        self._remote_cmds_start_wait_ready()
        self.async_run_with_timeout(self.remote_cmds._emit(""))
        self._remote_cmds_start_wait_stopped(ws_connect_mock.return_value, wait_for_delivered=False)

        sent_msgs = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertEqual(0, len(sent_msgs))

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    @patch('hummingbot.script.script_base.ScriptBase.on_remote_command_event')
    def test_remote_commands_scripting(self, mock_api, script_remote_evt_mock, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        done_callback_event = asyncio.Event()
        script_remote_evt_mock.side_effect = lambda evt: done_callback_event.set()
        ws_connect_mock.return_value = self._rce_setup()
        script_base = self._setup_script()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1",
                           "command": "balance"})

        task = asyncio.get_event_loop().create_task(script_base.listen_to_parent())

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        self.async_run_with_timeout(done_callback_event.wait(), timeout=0.5)

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

        self.assertEqual("test 1", self.remote_cmds.last_event_received.event_descriptor)
        self.assertTrue(self.remote_cmds._hb._script_iterator is not None)
        self.assertTrue(done_callback_event.is_set())

    @aioresponses()
    @patch('websockets.connect', new_callable=AsyncMock)
    def test_remote_commands_scripting_broadcasts(self, mock_api, ws_connect_mock):
        self._dummy_rest_responses(mock_api)
        ws_connect_mock.return_value = self._rce_setup()
        script_base = self._setup_script()

        self._ws_send_json(ws_connect_mock.return_value, {
                           "timestamp_event": 1234567891,
                           "event_descriptor": "test 1",
                           "command": "balance"})

        task = asyncio.get_event_loop().create_task(script_base.listen_to_parent())

        self._remote_cmds_start_and_stop_after_messages(ws_connect_mock.return_value)

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

        script_base.broadcast_remote_event(RemoteCmdEvent(event_descriptor="dummy script broadcast"))

        broadcasted_msg = script_base._child_queue.get()

        self.assertTrue(script_base._child_queue.empty())
        self.assertEqual("dummy script broadcast", broadcasted_msg.event_descriptor)
