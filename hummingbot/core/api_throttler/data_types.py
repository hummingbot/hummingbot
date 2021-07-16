from dataclasses import dataclass

DEFAULT_PATH = ""
DEFAULT_WEIGHT = 1


Limit = int             # Integer representing the no. of requests be time interval
RequestPath = str       # String representing the request path url
RequestWeight = int     # Integer representing the request weight of the path url
Seconds = float


@dataclass
class RateLimit():
    limit: Limit
    time_interval: Seconds
    path_url: RequestPath = DEFAULT_PATH
    weight: RequestWeight = DEFAULT_WEIGHT


@dataclass
class TaskLog():
    timestamp: float
    path_url: RequestPath = DEFAULT_PATH
    weight: RequestWeight = DEFAULT_WEIGHT
