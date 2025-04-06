try:
    from enum import StrEnum  # available from Python 3.11


    class ExchangeType(StrEnum):
        direct = 'direct'
        fanout = 'fanout'
        headers = 'headers'
        topic = 'topic'
except ImportError:
    from enum import Enum


    class ExchangeType(str, Enum):
        direct = 'direct'
        fanout = 'fanout'
        headers = 'headers'
        topic = 'topic'
