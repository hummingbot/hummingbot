import asyncio
from typing import Any, Generator

from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest

from .candle_data import CandleData
from .protocols import ProtocolForWSOperations, ProtocolWSAssistant, ProtocolWSOperationsWithMixin
from .utils import sanitize_data, yield_candle_data_from_dict


def parse_websocket_message(data: dict[str, Any]) -> Generator[CandleData, Any, None]:
    if not isinstance(data, dict):
        return
    if "events" not in data:
        return
    for event in data["events"]:
        if not isinstance(event, dict):
            continue
        if "candles" not in event:
            continue
        yield from yield_candle_data_from_dict(event)


class MixinWSOperations:
    def ws_subscription_payload(self: ProtocolForWSOperations):
        return {
            "type": "subscribe",
            "product_ids": [self._ex_trading_pair],
            "channel": "candles",
        }

    async def _catsc_listen_for_subscriptions(self: ProtocolWSOperationsWithMixin) -> None:
        """ Listens for new subscriptions and unsubscribes. """
        ws: ProtocolWSAssistant | None = None
        while True:
            try:
                ws: ProtocolWSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._catsc_process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _catsc_process_websocket_messages(
            self: ProtocolForWSOperations,
            websocket_assistant: ProtocolWSAssistant
    ) -> None:
        """ Process incoming websocket messages. """

        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data

            if isinstance(data, WSJSONRequest):
                await websocket_assistant.send(request=data)
                continue

            raw_candles: tuple[CandleData, ...] = ()
            for candle in parse_websocket_message(data):
                raw_candles += (candle,)

            if not raw_candles:
                continue

            raw_candles = sanitize_data(
                raw_candles,
                interval_in_s=self.get_seconds_from_interval(self.interval),
            )
            await self._initialize_deque_from_sequence(raw_candles)
