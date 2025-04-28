from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData


@runtime_checkable
class ProtocolForRestWS(Protocol):
    interval: str

    def logger(self) -> Any:
        ...

    def get_seconds_from_interval(self, interval: str) -> int:
        ...

    async def _sleep(self, seconds: float) -> None:
        ...

    async def _update_deque_set_historical(
            self,
            candles: tuple[CandleData, ...],
            *,
            extend_left: bool = False,
    ) -> None:
        ...


@runtime_checkable
class ProtocolForRestOperations(ProtocolForRestWS, Protocol):
    @property
    def ready(self) -> bool:
        ...

    @property
    def candles_max_result_per_rest_request(self) -> Any:
        ...

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

    def _get_first_candle_timestamp(self) -> int | None:
        ...

    def _get_last_candle_timestamp(self) -> int | None:
        ...

    def _get_missing_timestamps(self) -> int:
        ...

    def ensure_timestamp_in_seconds(self, timestamp: float | None) -> float:
        ...


@runtime_checkable
class ProtocolWSAssistant(Protocol):
    async def send(self, request: Any) -> None:
        ...

    def iter_messages(self) -> AsyncGenerator[Any, None]:
        ...


@runtime_checkable
class ProtocolForWSOperations(Protocol):
    _ex_trading_pair: str

    async def _connected_websocket_assistant(self) -> ProtocolWSAssistant:
        ...

    async def _subscribe_channels(self, websocket_assistant: ProtocolWSAssistant) -> None:
        ...

    async def _on_order_stream_interruption(self, websocket_assistant: ProtocolWSAssistant) -> None:
        ...


@runtime_checkable
class ProtocolMixinRestOperations(Protocol):
    def _get_rest_candles_params(
            self,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = None,
    ) -> dict[str, Any]:
        ...

    async def _catsc_fill_historical_candles(self):
        """ Fills the historical candles. """
        ...

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
class ProtocolMixinWSOperations(ProtocolForRestWS, Protocol):
    def ws_subscription_payload(self: ProtocolForWSOperations) -> dict[str, Any]:
        ...

    async def _catsc_listen_for_subscriptions(self: ProtocolWSOperationsWithMixin) -> None:
        ...

    async def _catsc_process_websocket_messages(
            self: ProtocolForWSOperations,
            websocket_assistant: ProtocolWSAssistant
    ) -> None:
        ...
