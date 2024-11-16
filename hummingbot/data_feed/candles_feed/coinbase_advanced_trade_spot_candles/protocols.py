import logging
from asyncio import Event
from collections import deque
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData
from hummingbot.logger import HummingbotLogger


@runtime_checkable
class ProtocolForFetchCandleData(Protocol):
    _candles: deque
    _ws_candle_available: Event
    interval: str

    @property
    def ready(self) -> bool:
        ...

    @property
    def candles_max_result_per_rest_request(self) -> Any:
        ...

    # @property
    # def interval(self) -> str:
    #     ...

    @property
    def interval_in_seconds(self) -> int:
        ...

    @property
    def candles_url(self) -> str:
        ...

    @property
    def _rest_throttler_limit_id(self) -> str:
        ...

    @property
    def _api_factory(self) -> WebAssistantsFactory:
        ...

    def logger(self) -> HummingbotLogger | logging.Logger:
        ...

    def ensure_timestamp_in_seconds(self, timestamp: float | None) -> float:
        ...

    def get_seconds_from_interval(self, interval: str) -> int:
        ...

    def _get_rest_candles_params(
            self,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = None,
    ) -> dict[str, Any]:
        ...

    async def _catsc_fill_historical_candles(self) -> None:
        ...

    async def _sleep(self, seconds: float) -> None:
        ...


@runtime_checkable
class ProtocolWSAssistant(Protocol):
    async def send(self, request: Any) -> None:
        ...

    def iter_messages(self) -> AsyncGenerator[Any, None]:
        ...


@runtime_checkable
class ProtocolForWSOperations(Protocol):
    interval: str
    _ex_trading_pair: str

    def get_seconds_from_interval(self, interval: str) -> int:
        ...

    async def _connected_websocket_assistant(self) -> ProtocolWSAssistant:
        ...

    async def _subscribe_channels(self, websocket_assistant: ProtocolWSAssistant) -> None:
        ...

    async def _initialize_deque_from_sequence(self, sequence: tuple[CandleData, ...]) -> None:
        ...

    async def _on_order_stream_interruption(self, websocket_assistant: ProtocolWSAssistant) -> None:
        ...

    def logger(self) -> Any:
        ...

    async def _sleep(self, seconds: float) -> None:
        ...


@runtime_checkable
class ProtocolMixinFetchCandleData(Protocol):
    async def _fetch_candles(
            self,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = None,
    ) -> tuple[CandleData, ...]:
        ...


class ProtocolWSOperationsWithMixin(
    ProtocolForWSOperations,
    Protocol,
):
    async def _catsc_process_websocket_messages(self, websocket_assistant: ProtocolWSAssistant) -> None:
        ...


@runtime_checkable
class ProtocolMixinWSOperations(Protocol):
    def ws_subscription_payload(self: ProtocolForWSOperations) -> dict[str, Any]:
        ...

    async def _catsc_listen_for_subscriptions(self: ProtocolWSOperationsWithMixin) -> None:
        ...

    async def _catsc_process_websocket_messages(
            self: ProtocolForWSOperations,
            websocket_assistant: ProtocolWSAssistant
    ) -> None:
        ...
