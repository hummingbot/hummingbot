import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Sequence, Tuple

from neutronx_sdk import Network
from neutronx_sdk.indexer import StreamFrame, ping_message, subscribe_message, unsubscribe_message
from neutronx_sdk.indexer.api import PING_INTERVAL_SECONDS

from hummingbot.connector.derivative.neutronx_perpetual import (
    neutronx_perpetual_constants as CONSTANTS,
    neutronx_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

Subscription = Tuple[str, str]


async def connect(api_factory: WebAssistantsFactory, network: Network, api_key: Optional[str] = None) -> WSAssistant:
    ws = await api_factory.get_ws_assistant()
    await ws.connect(
        ws_url=web_utils.indexer_ws_url(network),
        ping_timeout=PING_INTERVAL_SECONDS,
        message_timeout=CONSTANTS.WS_HEARTBEAT_TIMEOUT,
        ws_headers=web_utils.indexer_headers(api_key),
    )
    return ws


async def subscribe(ws: WSAssistant, subscriptions: Iterable[Subscription]) -> None:
    for channel, stream_id in subscriptions:
        await ws.send(WSJSONRequest(payload=subscribe_message(channel, stream_id)))


async def unsubscribe(ws: WSAssistant, subscriptions: Iterable[Subscription]) -> None:
    for channel, stream_id in subscriptions:
        await ws.send(WSJSONRequest(payload=unsubscribe_message(channel, stream_id)))


async def send_ping(ws: WSAssistant) -> None:
    await ws.send(WSJSONRequest(payload=ping_message()))


async def _heartbeat(ws: WSAssistant) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        await send_ping(ws)


@asynccontextmanager
async def heartbeat(ws: WSAssistant) -> AsyncIterator[None]:
    task = asyncio.ensure_future(_heartbeat(ws))
    try:
        yield
    finally:
        task.cancel()


def parse_frame(message: Dict[str, Any], logger: logging.Logger) -> StreamFrame:
    frame = StreamFrame.from_json(message)
    if frame.is_error:
        logger.warning(f"NeutronX indexer refused a stream request: {frame.code} {frame.message}")
    return frame


def group(subscriptions: Sequence[Subscription], size: int) -> List[List[Subscription]]:
    return [list(subscriptions[start:start + size]) for start in range(0, len(subscriptions), max(1, size))]
