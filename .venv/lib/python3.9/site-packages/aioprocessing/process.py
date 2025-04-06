from .executor import CoroBuilder
from .mp import Process

__all__ = ["AioProcess"]


class AioProcess(metaclass=CoroBuilder):
    delegate = Process
    coroutines = ["join"]
