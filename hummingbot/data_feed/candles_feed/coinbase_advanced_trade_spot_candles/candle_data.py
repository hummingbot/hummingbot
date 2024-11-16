from dataclasses import InitVar, dataclass, field
from datetime import datetime, timezone
from typing import ClassVar


@dataclass
class CandleData:
    """A class representing candle data structure.

    :param timestamp: The candle timestamp in seconds (can be int, float, str, or datetime)
    :param open: Opening price
    :param high: Highest price during period
    :param low: Lowest price during period
    :param close: Closing price
    :param volume: Trading volume
    :param quote_asset_volume: Quote asset volume
    :param n_trades: Number of trades
    :param taker_buy_base_volume: Base asset volume from taker buys
    :param taker_buy_quote_volume: Quote asset volume from taker buys
    :raises ValueError: If timestamp cannot be converted to int
    """
    timestamp_raw: InitVar[int | float | str | datetime]

    timestamp: int = field(init=False)
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_asset_volume: float = 0.0
    n_trades: int = 0
    taker_buy_base_volume: float = 0.0
    taker_buy_quote_volume: float = 0.0

    _timestamp_keys: ClassVar[tuple[str, ...]] = ('timestamp', 'time', 't')
    _price_keys: ClassVar[dict[str, tuple[str, ...]]] = {
        'open': ('open', 'o'),
        'high': ('high', 'h'),
        'low': ('low', 'l'),
        'close': ('close', 'c'),
        'volume': ('volume', 'v'),
    }

    @staticmethod
    def to_utc_seconds(dt: datetime) -> int:
        """Convert datetime to UTC timestamp in seconds.

        :param dt: Datetime to convert
        :returns: UTC timestamp in seconds
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.astimezone(timezone.utc).timestamp())

    @staticmethod
    def _normalize_timestamp(ts: int | float | str | datetime) -> int:
        """Convert various timestamp formats to integer seconds.

        :param ts: Timestamp in various formats
        :returns: Timestamp as integer seconds
        :raises ValueError: If timestamp cannot be converted
        """
        if isinstance(ts, int):
            return ts
        elif isinstance(ts, float):
            return int(ts)
        elif isinstance(ts, str):
            try:
                # Try parsing as Unix timestamp first
                return int(float(ts))
            except ValueError:
                try:
                    # Try parsing as ISO format
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    return CandleData.to_utc_seconds(dt)
                except ValueError as e:
                    raise ValueError(f"Could not parse timestamp string: {ts}") from e
        elif isinstance(ts, datetime):
            return CandleData.to_utc_seconds(ts)
        else:
            raise ValueError(f"Unsupported timestamp type: {type(ts)}")

    def __post_init__(self, timestamp_raw: int | float | str | datetime) -> None:
        """Convert timestamp to integer seconds after initialization.

        :param timestamp_raw: Raw timestamp input
        """
        self.timestamp = self._normalize_timestamp(timestamp_raw)

    @classmethod
    def create(cls, data: dict) -> 'CandleData':
        """Create CandleData from a dictionary.

        :param data: Dictionary containing candle data
        :type data: dict
        :returns: New CandleData instance
        :raises ValueError: If required fields are missing or invalid
        """
        timestamp_raw = next(
            (data[key] for key in cls._timestamp_keys if key in data), None
        )
        if timestamp_raw is None:
            raise ValueError(f"No timestamp found in keys: {cls._timestamp_keys}")

        # Find price values
        values = {}
        for f, keys in cls._price_keys.items():
            value = next((float(data[key]) for key in keys if key in data), None)
            if value is None:
                raise ValueError(f"No {f} value found in keys: {keys}")
            values[f] = value

        # Optional fields
        optional = {
            'quote_asset_volume': float(data.get('quote_asset_volume', 0)),
            'n_trades': int(data.get('n_trades', 0)),
            'taker_buy_base_volume': float(data.get('taker_buy_base_volume', 0)),
            'taker_buy_quote_volume': float(data.get('taker_buy_quote_volume', 0))
        }

        return cls(
            timestamp_raw=timestamp_raw,
            **values,
            **optional
        )

    def to_float_array(self) -> list[float]:
        """Convert CandleData to a list of values.

        :returns: List of candle values
        """
        return [
            float(self.timestamp),
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.quote_asset_volume,
            self.n_trades,
            self.taker_buy_base_volume,
            self.taker_buy_quote_volume
        ]
