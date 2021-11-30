from enum import Enum


class OrderState(Enum):
    UNSENT = 100
    PENDING = 200
    ACTIVE = 300
    PARTIAL_FILL = 325
    TO_CANCEL = 350
    PENDING_CANCEL = 400
    PENDING_PARTIAL_TO_FULL = 450
    HANGING = 475
    COMPLETE = 500
    CANCELED = 600
    FAILED = 700
    REVERSE_UNSENT = 800
    REVERSE_PENDING = 900
    REVERSE_PARTIAL_TO_CANCEL = 950
    REVERSE_ACTIVE = 1000
    REVERSE_COMPLETE = 1100
    REVERSE_FAILED = 1200

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
