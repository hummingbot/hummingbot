from enum import Enum


class DydxOrderStatus(Enum):
    PENDING = 0
    active = 100
    OPEN = 101
    PARTIALLY_FILLED = 102
    done = 300
    FILLED = 301
    failed = 400
    expired = 501
    CANCELED = 502

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
