from dataclasses import dataclass


@dataclass
class RateLimit():
    limit: int
    time_interval: float
    path_url: str = ""
    weight: int = 1


@dataclass
class TaskLog():
    timestamp: float
    path_url: str = ""
    weight: int = 1


Limit = int             # Integer representing the no. of requests be time interval
RequestPath = str       # String representing the request path url
RequestWeight = int     # Integer representing the request weight of the path url

Seconds = float
