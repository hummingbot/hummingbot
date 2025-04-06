from pydantic import BaseModel


class CandlesConfig(BaseModel):
    """
    The CandlesConfig class is a data class that stores the configuration of a Candle object.
    It has the following attributes:
    - connector: str
    - trading_pair: str
    - interval: str
    - max_records: int
    """
    connector: str
    trading_pair: str
    interval: str = "1m"
    max_records: int = 500


class HistoricalCandlesConfig(BaseModel):
    connector_name: str
    trading_pair: str
    interval: str
    start_time: int
    end_time: int
