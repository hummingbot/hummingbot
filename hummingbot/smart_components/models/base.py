from enum import Enum


class SmartComponentStatus(Enum):
    NOT_STARTED = 1
    RUNNING = 2
    SHUTTING_DOWN = 3
    TERMINATED = 4
