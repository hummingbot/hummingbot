from decimal import Decimal
from typing import Any, Dict, Iterable, Optional, Tuple

from services.event_bus import EventBus
from services.indicators import IndicatorState


class MarketDataService:
    """
    Subscribes to Hyperliquid websocket market data, maintains rolling indicators per symbol/timeframe,
    and publishes derived metrics (close price, EMA fast/slow, ATR) to the shared EventBus.
    """

    def __init__(
        self,
        hl_client: Any,
        bus: EventBus,
        symbols: Iterable[str],
        timeframes: Iterable[str],
        fast_period: int = 12,
        slow_period: int = 26,
        atr_period: int = 14,
    ):
        self._client = hl_client
        self._bus = bus
        self._symbols = list(symbols)
        self._timeframes = list(timeframes)
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._atr_period = atr_period
        self._indicator_state: Dict[Tuple[str, str], IndicatorState] = {}

    async def run(self):
        await self._client.connect(symbols=self._symbols, timeframes=self._timeframes)
        async for message in self._client.messages():
            await self._handle_message(message)

    async def _handle_message(self, message: Dict[str, Any]):
        parsed = self._parse_message(message)
        if parsed is None:
            return
        symbol, timeframe, high, low, close, timestamp = parsed
        state = self._indicator_state.setdefault(
            (symbol, timeframe),
            IndicatorState(self._fast_period, self._slow_period, self._atr_period),
        )
        state.update(high=high, low=low, close=close, timestamp=timestamp)
        snapshot = state.snapshot()
        if snapshot is None:
            return
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "close": float(close),
            **snapshot,
        }
        topic = f"md.{symbol}.{timeframe}"
        await self._bus.publish(topic, payload)

    def _parse_message(self, message: Dict[str, Any]) -> Optional[Tuple[str, str, Decimal, Decimal, Decimal, int]]:
        candle = message.get("candle") or message.get("kline") or message
        symbol = candle.get("symbol") or message.get("symbol")
        timeframe = candle.get("timeframe") or message.get("timeframe")
        if symbol is None or timeframe is None:
            return None
        try:
            high = Decimal(str(candle["high"]))
            low = Decimal(str(candle["low"]))
            close = Decimal(str(candle["close"]))
            timestamp = int(candle.get("timestamp") or candle.get("ts"))
        except Exception:
            return None
        return symbol, timeframe, high, low, close, timestamp
