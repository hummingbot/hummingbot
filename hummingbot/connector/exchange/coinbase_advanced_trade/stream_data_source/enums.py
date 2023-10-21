from enum import Enum


class StreamState(Enum):
    CLOSED = "CLOSED"
    OPENED = "OPENED"
    SUBSCRIBED = "SUBSCRIBED"
    UNSUBSCRIBED = "UNSUBSCRIBED"


class StreamAction(Enum):
    SUBSCRIBE = "Subscribe"
    UNSUBSCRIBE = "Unsubscribe"
