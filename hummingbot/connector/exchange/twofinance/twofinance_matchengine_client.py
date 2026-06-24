from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from hummingbot.connector.exchange.twofinance.twofinance_matchengine_schemas import (
    CommandResponse,
    MatchEngineEvent,
    OrderCommand,
    is_command_response,
    parse_command_response,
)
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


@dataclass
class MatchEngineOrderEntry:
    client_order_id: str
    command: OrderCommand
    exchange_order_id: str | None = None
    last_response: CommandResponse | None = None
    last_event: MatchEngineEvent | None = None


@dataclass
class MatchEngineClient:
    api_factory: WebAssistantsFactory
    ws_url: str
    auth_headers: dict[str, str] = field(default_factory=dict)
    orders: dict[str, MatchEngineOrderEntry] = field(default_factory=dict)
    orders_by_exchange_id: dict[str, str] = field(default_factory=dict)
    last_sequence: int = 0
    _ws_assistant: Any | None = None

    async def send_command(self, command: OrderCommand) -> None:
        self.orders.setdefault(command.client_order_id, MatchEngineOrderEntry(command.client_order_id, command))
        ws = await self._connected_ws_assistant()
        await ws.send(WSJSONRequest(payload=command.to_payload()))

    async def receive_once(self) -> CommandResponse | MatchEngineEvent:
        ws = await self._connected_ws_assistant()
        response = await ws.receive()
        if response is None:
            raise ConnectionError("MatchEngine WebSocket disconnected")
        data = response.data
        if not isinstance(data, dict):
            raise ValueError("MatchEngine WebSocket payload must be a JSON object")
        if is_command_response(data):
            command_response = parse_command_response(data)
            self.apply_command_response(command_response)
            return command_response
        event = MatchEngineEvent.from_payload(data)
        self.apply_event(event)
        return event

    async def wait_for_ack(self, client_order_id: str, timeout_seconds: float) -> CommandResponse | None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            entry = self.orders.get(client_order_id)
            if entry is not None and entry.last_response is not None:
                return entry.last_response
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return None
            try:
                await asyncio.wait_for(self.receive_once(), timeout=min(remaining, 0.1))
            except asyncio.TimeoutError:
                await asyncio.sleep(0)

    def apply_command_response(self, response: CommandResponse) -> None:
        if response.client_order_id is None:
            return
        entry = self.orders.get(response.client_order_id)
        if entry is None:
            return
        entry.last_response = response
        if response.order_id is not None:
            entry.exchange_order_id = response.order_id
            self.orders_by_exchange_id[response.order_id] = response.client_order_id

    def apply_event(self, event: MatchEngineEvent) -> None:
        if event.sequence > self.last_sequence:
            self.last_sequence = event.sequence
        client_order_id = event.payload.get("client_order_id")
        exchange_order_id = event.payload.get("order_id") or event.payload.get("new_order_id")
        if client_order_id is None and exchange_order_id is not None:
            client_order_id = self.orders_by_exchange_id.get(str(exchange_order_id))
        if client_order_id is None:
            return
        entry = self.orders.get(str(client_order_id))
        if entry is None:
            return
        entry.last_event = event
        if exchange_order_id is not None:
            entry.exchange_order_id = str(exchange_order_id)
            self.orders_by_exchange_id[str(exchange_order_id)] = str(client_order_id)

    async def close(self) -> None:
        if self._ws_assistant is not None:
            await self._ws_assistant.disconnect()
            self._ws_assistant = None

    async def _connected_ws_assistant(self):
        if self._ws_assistant is None:
            self._ws_assistant = await self.api_factory.get_ws_assistant()
        if not self._ws_assistant._connection.connected:
            await self._ws_assistant.connect(ws_url=self.ws_url, ws_headers=self.auth_headers)
        return self._ws_assistant
