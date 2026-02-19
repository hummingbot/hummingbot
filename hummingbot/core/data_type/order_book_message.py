from enum import Enum

class OrderBookMessageType(Enum):
    SNAPSHOT = 1
    DIFF = 2

class OrderBookMessage:
    def __init__(self, type, content, timestamp=None):
        self.type = type
        self.content = content
        self.timestamp = timestamp
        self.bids = content.get('bids', [])
        self.asks = content.get('asks', [])
        self.update_id = content.get('update_id')
