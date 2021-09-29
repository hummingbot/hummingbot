import asyncio
import logging
import re
import socket
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
    Set,
)
import hummingbot
from hummingbot.logger import HummingbotLogger
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.event.events import (
    RemoteEvent,
    RemoteCmdEvent)
from hummingbot.core.pubsub import PubSub
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future


DISABLED_COMMANDS = {
    "connect",             # disabled
    "create",              # disabled
    "import",              # disabled
    "export",              # disabled
}


class RemoteCommandExecutor(PubSub):
    rce_logger: Optional[HummingbotLogger] = None
    _rce_shared_instance = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.rce_logger is None:
            cls.rce_logger = logging.getLogger(__name__)
        return cls.rce_logger

    @classmethod
    def get_instance(cls) -> "RemoteCommandExecutor":
        if cls._rce_shared_instance is None:
            cls._rce_shared_instance = RemoteCommandExecutor()
        return cls._rce_shared_instance

    def __init__(self,
                 api_key: str = None,
                 ws_url: str = None,) -> None:
        self._api_key: str = api_key or global_config_map.get("remote_commands_api_key").value
        self._ws_url: str = ws_url or global_config_map.get("remote_commands_ws_url").value
        self._ignore_first_event: bool = global_config_map.get("remote_commands_ignore_first_event").value
        self._disable_console_commands: bool = global_config_map.get("remote_commands_disable_console_commands").value
        self._routing_name: Optional[str] = global_config_map.get("remote_commands_routing_name").value
        self._cmd_translate_dict: Optional[Dict[str, str]] = global_config_map.get("remote_commands_translate_commands").value
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_timeout: int = 1200
        self._alpha_num = re.compile(r"^[a-zA-Z0-9 _\-]+$")
        self._processed_events: Optional[Set[int]] = set()
        self._started: bool = False
        self._first_event_received: bool = False
        self._last_event_received: Optional[RemoteCmdEvent] = None
        self._ev_loop = asyncio.get_event_loop()
        self._rce_task = None

    @property
    def _hb(self) -> "hummingbot.client.hummingbot_application.HummingbotApplication":
        from hummingbot.client.hummingbot_application import HummingbotApplication
        return HummingbotApplication.main_application()

    @property
    def started(self) -> bool:
        return self._started

    @property
    def last_event_received(self) -> Optional[RemoteCmdEvent]:
        return self._last_event_received

    async def connect(self):
        """
        Connect to Remote Commands websocket.
        """
        auth_headers = {
            "User-Agent": "hummingbot",
            "HBOT-API-KEY": self._api_key,
        }
        self._client = await websockets.connect(self._ws_url, extra_headers=auth_headers)
        self.logger().info("Remote Command Executor is listening.")
        return self._client

    async def disconnect(self):
        """
        Disconnect from Remote Commands websocket.
        """
        if self._client is None:
            return
        await self._client.close()

    # receive & parse messages
    async def _messages(self) -> AsyncIterable[Any]:
        """
        Receive and parse messages
        """
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(self._client.recv(), timeout=self._ws_timeout)
                    try:
                        json_data = ujson.loads(msg)
                        yield json_data
                    except ValueError:
                        # If data is not json yield strings as json
                        if self._alpha_num.match(msg):
                            yield {
                                "timestamp_received": int(time.time() * 1e3),
                                "command": msg,
                            }
                        else:
                            continue
                except asyncio.TimeoutError:
                    await asyncio.wait_for(self._client.ping(), timeout=self._ws_timeout)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()

    async def _process_event(self, event):
        """
        Process and handle incoming events
        """
        remote_event = RemoteCmdEvent.from_json_data(event)

        # Event ID for event set.
        event_id = f"{remote_event.timestamp_received}{remote_event.timestamp_event}"

        # Skip Processed events
        if event_id in self._processed_events:
            return

        # Add to processed event set
        self._processed_events.add(event_id)

        # Handle first event, skip if set.
        if not self._first_event_received:
            self._first_event_received = True
            if self._ignore_first_event:
                return

        # Skip unmatched events if set.
        if self._routing_name and remote_event.event_descriptor:
            if self._routing_name != remote_event.event_descriptor:
                return

        # Translate command string based on config.
        command_log_string = remote_event.command
        if self._cmd_translate_dict:
            remote_event.translate_commands(self._cmd_translate_dict)
            if command_log_string != remote_event.command:
                command_log_string = f"{command_log_string} -> {remote_event.command}"

        # Set last event
        self._last_event_received = remote_event

        # Send event to script iterator
        if self._hb._script_iterator is not None:
            self._hb._script_iterator.process_remote_command_event(remote_event)

        # Trigger event for event reporter
        self.trigger_event(RemoteEvent.RemoteCmdEvent, remote_event)

        # Process general hummingbot commands if enabled and there is one.
        if not self._disable_console_commands and remote_event.command:
            self._hb.app.log(f"\n[Remote Command Executor] {command_log_string}")

            # if the command does starts with any disabled commands
            if any([remote_event.command.lower().startswith(dc) for dc in DISABLED_COMMANDS]):
                return
            else:
                async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
                await async_scheduler.call_async(self._hb._handle_command, remote_event.command)
        return

    async def _emit(self, remote_event):
        """
        Emit messages *to* the websocket.
        """
        # Only emit `RemoteCmdEvent` objects.
        if not isinstance(remote_event, RemoteCmdEvent):
            return

        payload = {
            **remote_event.__dict__,
            # Use `timestamp_event` here, not `timestamp_received`
            "timestamp_event": int(time.time() * 1e3),
        }
        await self._client.send(ujson.dumps(payload))
        return True

    def broadcast(self, remote_event):
        # Only broadcast `RemoteCmdEvent` objects.
        if not isinstance(remote_event, RemoteCmdEvent):
            return
        safe_ensure_future(self._emit(remote_event), loop=self._ev_loop)
        return True

    async def listen_loop(self) -> None:
        while True:
            try:
                await self.connect()
                async for response in self._messages():
                    try:
                        await self._process_event(response)
                    except Exception as e:
                        self._hb.app.log(f"\n[Remote Command Executor] Error: {e}")
                        self.logger().error(f"Remote Command Executor error: {e}", exc_info=True)
            except asyncio.CancelledError:
                raise
            except (websockets.exceptions.InvalidStatusCode, socket.gaierror):
                self.logger().error("Error connecting to websocket, invalid URL or API key, cannot continue.")
                raise
            except (websockets.exceptions.InvalidMessage, OSError):
                self.logger().error("Error connecting to websocket, sleeping 10.")
                await asyncio.sleep(10.0)
            except Exception:
                self.logger().error("Unexpected error in websocket, sleeping 20.", exc_info=True)
                await asyncio.sleep(20.0)
            finally:
                await self.disconnect()

    def start(self):
        if not self._started:
            self._started = True
            self.logger().info("Starting Remote Command Executor.")
            self._rce_task = safe_ensure_future(self.listen_loop(), loop=self._ev_loop)

    def stop(self) -> None:
        if self._started:
            safe_ensure_future(self.disconnect())
            self._started = False
            self._rce_task.cancel()
            self._rce_task = None

    # Only used for testing websocket data in the test suite.
    async def _on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
