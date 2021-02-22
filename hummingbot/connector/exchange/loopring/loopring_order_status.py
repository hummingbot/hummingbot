from enum import Enum


class LoopringOrderStatus(Enum):
    waiting = 0
    ACTIVE = 100
    processing = 101
    cancelling = 200
    DONE = 300
    processed = 301
    failed = 400
    cancelled = 402
    expired = 403

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented
