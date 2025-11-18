from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class IndicatorState:
    """
    Maintains EMA fast/slow values plus ATR for a single symbol/timeframe pair.
    Uses the standard Wilder smoothing for ATR and rolling EMA for the moving averages.
    """

    fast_period: int
    slow_period: int
    atr_period: int
    ema_fast: Optional[Decimal] = None
    ema_slow: Optional[Decimal] = None
    atr: Optional[Decimal] = None
    last_close: Optional[Decimal] = None
    last_high: Optional[Decimal] = None
    last_low: Optional[Decimal] = None
    last_timestamp: Optional[int] = None
    _fast_alpha: Decimal = field(init=False)
    _slow_alpha: Decimal = field(init=False)
    _atr_alpha: Decimal = field(init=False)

    def __post_init__(self):
        if self.fast_period <= 0 or self.slow_period <= 0 or self.atr_period <= 0:
            raise ValueError("Indicator periods must be positive.")
        self._fast_alpha = Decimal("2") / Decimal(self.fast_period + 1)
        self._slow_alpha = Decimal("2") / Decimal(self.slow_period + 1)
        self._atr_alpha = Decimal("1") / Decimal(self.atr_period)

    def update(self, high: Decimal, low: Decimal, close: Decimal, timestamp: int):
        """
        Update EMA/ATR internal state with the latest candle values.
        """
        high = Decimal(high)
        low = Decimal(low)
        close = Decimal(close)
        self.last_timestamp = timestamp
        self.last_high = high
        self.last_low = low
        self.last_close = close

        if self.ema_fast is None:
            self.ema_fast = close
        else:
            self.ema_fast = (close - self.ema_fast) * self._fast_alpha + self.ema_fast

        if self.ema_slow is None:
            self.ema_slow = close
        else:
            self.ema_slow = (close - self.ema_slow) * self._slow_alpha + self.ema_slow

        true_range = self._true_range(high, low, close)
        if self.atr is None:
            self.atr = true_range
        else:
            self.atr = (self.atr * (Decimal("1") - self._atr_alpha)) + true_range * self._atr_alpha

    def snapshot(self) -> Optional[dict]:
        if self.ema_fast is None or self.ema_slow is None or self.atr is None or self.last_timestamp is None:
            return None
        return {
            "ema_fast": float(self.ema_fast),
            "ema_slow": float(self.ema_slow),
            "atr": float(self.atr),
            "timestamp": self.last_timestamp,
        }

    def _true_range(self, high: Decimal, low: Decimal, close: Decimal) -> Decimal:
        if self.last_close is None:
            return high - low
        return max(
            high - low,
            abs(high - self.last_close),
            abs(low - self.last_close),
        )
